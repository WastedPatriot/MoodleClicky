"""Wires it all together: hotkeys + tray icon -> screenshot -> Claude -> buddy + pop-up."""

from __future__ import annotations

import logging
import os
import queue
import subprocess  # nosec B404 - only used to open the notes folder
import sys
import threading
import tkinter as tk
from collections.abc import Callable

from moodleclicky import APP_NAME, __version__, capture, notes
from moodleclicky.brain import Explanation, Tutor, has_key
from moodleclicky.bubble import Bubble, Page
from moodleclicky.buddy import Buddy
from moodleclicky.config import Settings, data_dir
from moodleclicky.settings_ui import SettingsWindow
from moodleclicky.triggers import KeyTrigger
from moodleclicky.winutil import SingleInstance, enable_dpi_awareness, focus_window, foreground_window, set_autostart

log = logging.getLogger(APP_NAME)


class App:
    def __init__(self, root: tk.Tk, settings: Settings, tutor: Tutor | None = None,
                 enable_hotkeys: bool = True, enable_tray: bool = True):
        self.root = root
        self.settings = settings
        self.mode = settings.mode
        self.tutor = tutor or Tutor(settings)
        self.jobs: queue.Queue[Callable[[], None]] = queue.Queue()
        self.busy = False
        self.last_question = ""
        self._hotkeys = None
        self._tray = None
        self._settings_win: SettingsWindow | None = None
        self._notetaker = None
        self._trigger: KeyTrigger | None = None
        self.target_hwnd: int | None = None  # the window you were typing in when you called the buddy
        self._return_focus = False  # quick-trigger looks hand the keyboard straight back to your box

        self.buddy = Buddy(root, settings.buddy_color)
        self.bubble = Bubble(
            root,
            on_ask=self.ask,
            on_follow_up=self.follow_up,
            on_settings=self.open_settings,
            on_page=self._on_page,
            on_close=self.buddy.follow,
            get_mode=lambda: self.mode,
            set_mode=self._set_mode,
            on_type=self.type_suggestion,
            type_hint=trigger_hint(settings),
        )
        if not settings.buddy_visible:
            self.buddy.hide()
        if enable_hotkeys:
            self._start_hotkeys()
            self._start_trigger()
        if enable_tray:
            self._start_tray()
        self._pump()

    # ---- thread-safe hop onto the Tk thread ----------------------------
    def call_soon(self, fn: Callable[[], None]) -> None:
        self.jobs.put(fn)

    def _pump(self) -> None:
        try:
            while True:
                self.jobs.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(40, self._pump)

    # ---- actions -------------------------------------------------------
    def on_trigger(self) -> None:
        """Double-tap Ctrl (or your chosen trigger): type the suggestion if one is up, else look now."""
        if self.bubble.state == "showing" and self.bubble.type_text:
            self.type_suggestion()
        elif self.settings.instant:
            self.look_now()
        else:
            self.start_prompt()

    def look_now(self) -> None:
        """No questions asked: screenshot what's under the mouse and explain it."""
        if self.busy:
            return
        if not self.tutor.ready:
            self.open_settings()
            return
        self.target_hwnd = foreground_window()
        self._return_focus = True
        self.ask("")

    def type_suggestion(self) -> None:
        text = self.bubble.type_text
        if not text:
            return
        from moodleclicky.typer import type_into

        try:
            type_into(self.root, self.target_hwnd, text, pause=self._pause_trigger)
            self.bubble.footer.config(text="✓ Typed into your box. Ctrl+Z undoes it.")
            self.bubble.set_type_text("")
        except Exception as e:  # keyboard hook unavailable etc.
            log.exception("typing failed")
            self.bubble.footer.config(text=f"Couldn't type it ({e}) - it's on your clipboard instead.")

    def _pause_trigger(self, on: bool) -> None:
        if self._trigger:
            self._trigger.tap.paused = on

    def start_prompt(self) -> None:
        """Hotkey: pop up next to the cursor and ask what's up."""
        if self.busy:
            return
        if not self.tutor.ready:
            self.open_settings()
            return
        if not self.buddy.visible and self.settings.buddy_visible:
            self.buddy.show()
        self.buddy.follow()
        self.target_hwnd = foreground_window()
        self._return_focus = False  # the prompt needs the keyboard
        self.bubble.prompt(self.root.winfo_pointerxy())

    def ask(self, question: str) -> None:
        if self.busy:
            return
        self.busy = True
        self.last_question = question
        cursor = self.root.winfo_pointerxy()
        # Hide our own windows so they aren't in the screenshot.
        was_visible = self.bubble.state != "hidden" or self.buddy.visible
        self.bubble.win.withdraw()
        self.buddy.win.withdraw()
        self.root.update()
        partial = lambda f: self.call_soon(lambda: self.bubble.show_partial(f))  # noqa: E731

        def work() -> None:
            try:
                shot = capture.grab(cursor, self.settings.max_image_edge)
            except Exception as e:  # screen capture can fail on locked screens etc.
                failed = Explanation.failed(f"Couldn't capture the screen: {e}")
                self.call_soon(lambda: self._show_result(failed, cursor))
                return
            self.call_soon(lambda: self._thinking(cursor))
            exp = self.tutor.ask(shot, question, self.mode, on_partial=partial)
            self.call_soon(lambda: self._show_result(exp, cursor))

        # Give Windows a moment to actually remove our windows from the screen before the screenshot.
        self.root.after(60 if was_visible else 0, lambda: threading.Thread(target=work, daemon=True).start())

    def follow_up(self, text: str) -> None:
        if self.busy:
            return
        self.busy = True
        self.last_question = text
        self._return_focus = False
        near = self.buddy.position()
        self._thinking(None)

        partial = lambda f: self.call_soon(lambda: self.bubble.show_partial(f))  # noqa: E731

        def work() -> None:
            exp = self.tutor.follow_up(text, self.mode, on_partial=partial)
            self.call_soon(lambda: self._show_result(exp, near))

        threading.Thread(target=work, daemon=True).start()

    def toggle_buddy(self) -> None:
        self.settings.buddy_visible = not self.settings.buddy_visible
        self.settings.save()
        (self.buddy.show if self.settings.buddy_visible else self.buddy.hide)()
        if self._tray:
            self._tray.update_menu()

    def open_settings(self) -> None:
        if self._settings_win and self._settings_win.win.winfo_exists():
            self._settings_win.win.lift()
            return
        self._settings_win = SettingsWindow(self.root, self.settings, self._apply_settings, self.open_notes)

    def open_notetaker(self) -> None:
        if self._notetaker is None:
            from moodleclicky.lecture_ui import NotetakerWindow

            self._notetaker = NotetakerWindow(self.root, self.settings, self.call_soon, self.open_path)
        self._notetaker.show()

    def mark_moment(self) -> None:
        """Hotkey while recording: flag 'this bit matters' without opening anything."""
        if self._notetaker:
            self._notetaker.mark()

    def open_notes(self) -> None:
        self.open_path(str(notes.notes_dir()))

    def open_path(self, path: str) -> None:
        if sys.platform == "win32":
            os.startfile(path)  # nosec B606 - our own folder
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])  # nosec B603 B607
        else:
            subprocess.Popen(["xdg-open", path])  # nosec B603 B607

    def quit(self) -> None:
        nt = self._notetaker
        if nt and nt.session and nt.session.state in ("recording", "paused"):
            nt.session.stop()  # saves the last chunk; transcript so far is already on disk
        if self._hotkeys:
            self._hotkeys.stop()
        if self._trigger:
            self._trigger.stop()
        if self._tray:
            self._tray.stop()
        self.root.quit()

    # ---- internals -----------------------------------------------------
    def _thinking(self, cursor: tuple[int, int] | None) -> None:
        if self.settings.buddy_visible:
            self.buddy.show()
        self.buddy.follow()
        self.buddy.set_thinking(True)
        self.bubble.thinking(cursor)
        self._give_focus_back()

    def _give_focus_back(self) -> None:
        """Showing the pop-up mustn't steal your caret: return focus to the box you were typing in."""
        if self._return_focus and self.target_hwnd:
            self.root.after(30, lambda: focus_window(self.target_hwnd))

    def _show_result(self, exp: Explanation, near: tuple[int, int]) -> None:
        self.busy = False
        self.buddy.set_thinking(False)
        if self.settings.buddy_visible:
            self.buddy.show()
        footer = f"≈ ${exp.cost_usd:.3f} this answer · ${self.tutor.total_cost:.2f} this session"
        if self.settings.save_notes and not exp.error:
            try:
                notes.save(exp, self.last_question, self.mode)
                footer += " · saved to notes"
            except OSError:
                pass
        if exp.type_text and not exp.error:
            footer = f"{trigger_hint(self.settings)} types the suggestion · " + footer
        self.bubble.show_explanation(exp, near, self.settings.open_on_answer, footer)
        self._give_focus_back()

    def _on_page(self, page: Page | None) -> None:
        if page and page.point:
            self.buddy.point_at(page.point, page.label)
        else:
            self.buddy.follow()

    def _set_mode(self, mode: str) -> None:
        self.mode = mode

    def _apply_settings(self, s: Settings) -> None:
        self.settings = s
        self.tutor.settings = s
        self.tutor.reset_backend()
        self.mode = s.mode
        self.buddy.set_color(s.buddy_color)
        (self.buddy.show if s.buddy_visible else self.buddy.hide)()
        set_autostart(s.start_with_windows)
        if self._notetaker:
            self._notetaker.settings = s
        if self._hotkeys:
            self._hotkeys.stop()
            self._start_hotkeys()
        if self._trigger:
            self._trigger.stop()
            self._start_trigger()
        self.bubble.type_btn.config(text=f"Type it  ·  {trigger_hint(s)}")
        if self._tray:
            self._tray.update_menu()

    def _start_hotkeys(self) -> None:
        try:
            from pynput import keyboard

            s = self.settings
            keys = {}
            ask_fn = self.on_trigger if s.trigger == "hotkey" else self.start_prompt
            for combo, fn in ((s.hotkey_ask, ask_fn), (s.hotkey_toggle, self.toggle_buddy),
                              (s.hotkey_notes, self.open_notetaker), (s.hotkey_mark, self.mark_moment)):
                if combo and combo not in keys:
                    keys[combo] = lambda fn=fn: self.call_soon(fn)
            self._hotkeys = keyboard.GlobalHotKeys(keys)
            self._hotkeys.daemon = True
            self._hotkeys.start()
        except Exception:  # bad hotkey string or no keyboard hook available
            log.exception("hotkeys disabled")
            self._hotkeys = None

    def _start_trigger(self) -> None:
        if self.settings.trigger == "hotkey":
            self._trigger = None
            return
        try:
            self._trigger = KeyTrigger(self.settings.trigger, lambda: self.call_soon(self.on_trigger))
            self._trigger.start()
        except Exception:  # no keyboard hook available
            log.exception("double-tap trigger disabled")
            self._trigger = None

    def _start_tray(self) -> None:
        try:
            import pystray
        except Exception:
            log.exception("tray icon disabled")
            return
        item = pystray.MenuItem
        menu = pystray.Menu(
            item("Show / hide buddy", lambda: self.call_soon(self.toggle_buddy), default=True,
                 checked=lambda _i: self.settings.buddy_visible),
            item("Look at my screen now", lambda: self.call_soon(self.look_now)),
            item("Ask a question…", lambda: self.call_soon(self.start_prompt)),
            item("Lecture / meeting notetaker…", lambda: self.call_soon(self.open_notetaker)),
            item("Settings…", lambda: self.call_soon(self.open_settings)),
            item("Open revision notes", lambda: self.call_soon(self.open_notes)),
            pystray.Menu.SEPARATOR,
            item("Quit", lambda: self.call_soon(self.quit)),
        )
        self._tray = pystray.Icon(APP_NAME, tray_image(self.settings.buddy_color),
                                  f"{APP_NAME} {__version__}", menu)
        try:
            self._tray.run_detached()
        except Exception:
            log.exception("tray icon disabled")
            self._tray = None


def trigger_hint(s: Settings) -> str:
    return {"double_rctrl": "Right Ctrl ×2", "double_ctrl": "Ctrl ×2", "triple_ctrl": "Ctrl ×3",
            "right_ctrl": "Right Ctrl"}.get(
        s.trigger, "Ctrl+Alt+Space")


def tray_image(color: str):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = [(0, 0), (0, 34), (9, 26), (16, 42), (23, 39), (16, 24), (28, 24)]
    d.polygon([(10 + x * 1.2, 6 + y * 1.2) for x, y in pts], fill=color, outline="white")
    for ex, ey in ((16, 24), (23, 28)):
        d.ellipse((ex - 4, ey - 4, ex + 4, ey + 4), fill="white")
        d.ellipse((ex - 2, ey - 2, ex + 2, ey + 2), fill="black")
    return img


def setup_logging() -> None:
    """Everything (including crashes in any thread) goes to %APPDATA%\\MoodleClicky\\moodleclicky.log."""
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(data_dir() / "moodleclicky.log", maxBytes=1_000_000, backupCount=2,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])

    def hook(exc_type, exc, tb):
        log.error("unhandled error", exc_info=(exc_type, exc, tb))

    sys.excepthook = hook
    threading.excepthook = lambda a: hook(a.exc_type, a.exc_value, a.exc_traceback)


def _ensure_std_streams() -> None:
    """A windowed .exe has no console: sys.stdout/stderr are None and libraries that print (e.g. the
    speech-model download progress bar) would crash. Point them at devnull instead."""
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115 - lives for the process


def main() -> None:
    _ensure_std_streams()
    if "--apply-setup" in sys.argv:  # called by install.ps1 after its setup menu
        from moodleclicky.setup_cli import main as apply_main

        sys.exit(apply_main())
    if "--selftest" in sys.argv:
        from moodleclicky.selftest import run

        sys.exit(run(sys.argv[sys.argv.index("--selftest") + 1:]))
    setup_logging()
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()  # all our windows are Toplevels
    root.title(APP_NAME)
    root.report_callback_exception = lambda *exc: log.error("error in UI callback", exc_info=exc)
    settings = Settings.load()
    box: dict = {}
    instance = SingleInstance(on_poke=lambda: box["app"].call_soon(box["app"].start_prompt) if "app" in box
                              else None)
    if not instance.primary:
        return  # already running - the other copy pops up instead
    app = box["app"] = App(root, settings)
    if not has_key(settings):
        root.after(500, app.open_settings)
    log.info("%s %s running. %s = ask, %s = show/hide, %s = notetaker.", APP_NAME, __version__,
             settings.hotkey_ask, settings.hotkey_toggle, settings.hotkey_notes)
    root.mainloop()
