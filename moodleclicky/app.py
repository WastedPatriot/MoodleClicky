"""Wires it all together: hotkeys + tray icon -> screenshot -> Claude -> buddy + pop-up."""

from __future__ import annotations

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
from moodleclicky.config import Settings
from moodleclicky.settings_ui import SettingsWindow
from moodleclicky.winutil import enable_dpi_awareness


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
        )
        if not settings.buddy_visible:
            self.buddy.hide()
        if enable_hotkeys:
            self._start_hotkeys()
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
        self.bubble.prompt(self.root.winfo_pointerxy())

    def ask(self, question: str) -> None:
        if self.busy:
            return
        self.busy = True
        self.last_question = question
        cursor = self.root.winfo_pointerxy()
        # Hide our own windows so they aren't in the screenshot.
        self.bubble.win.withdraw()
        self.buddy.win.withdraw()
        self.root.update()

        def work() -> None:
            try:
                shot = capture.grab(cursor, self.settings.max_image_edge)
            except Exception as e:  # screen capture can fail on locked screens etc.
                failed = Explanation.failed(f"Couldn't capture the screen: {e}")
                self.call_soon(lambda: self._show_result(failed, cursor))
                return
            self.call_soon(lambda: self._thinking(cursor))
            exp = self.tutor.ask(shot, question, self.mode)
            self.call_soon(lambda: self._show_result(exp, cursor))

        self.root.after(120, lambda: threading.Thread(target=work, daemon=True).start())

    def follow_up(self, text: str) -> None:
        if self.busy:
            return
        self.busy = True
        self.last_question = text
        near = self.buddy.position()
        self._thinking(None)

        def work() -> None:
            exp = self.tutor.follow_up(text, self.mode)
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

    def open_notes(self) -> None:
        path = str(notes.notes_dir())
        if sys.platform == "win32":
            os.startfile(path)  # nosec B606 - our own folder
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])  # nosec B603 B607
        else:
            subprocess.Popen(["xdg-open", path])  # nosec B603 B607

    def quit(self) -> None:
        if self._hotkeys:
            self._hotkeys.stop()
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
        self.bubble.show_explanation(exp, near, self.settings.open_on_answer, footer)

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
        if self._hotkeys:
            self._hotkeys.stop()
            self._start_hotkeys()
        if self._tray:
            self._tray.update_menu()

    def _start_hotkeys(self) -> None:
        try:
            from pynput import keyboard

            self._hotkeys = keyboard.GlobalHotKeys({
                self.settings.hotkey_ask: lambda: self.call_soon(self.start_prompt),
                self.settings.hotkey_toggle: lambda: self.call_soon(self.toggle_buddy),
            })
            self._hotkeys.daemon = True
            self._hotkeys.start()
        except Exception as e:  # bad hotkey string or no keyboard hook available
            print(f"[{APP_NAME}] hotkeys disabled: {e}", file=sys.stderr)
            self._hotkeys = None

    def _start_tray(self) -> None:
        try:
            import pystray
        except Exception as e:
            print(f"[{APP_NAME}] tray icon disabled: {e}", file=sys.stderr)
            return
        item = pystray.MenuItem
        menu = pystray.Menu(
            item("Show / hide buddy", lambda: self.call_soon(self.toggle_buddy), default=True,
                 checked=lambda _i: self.settings.buddy_visible),
            item("Ask about my screen", lambda: self.call_soon(self.start_prompt)),
            item("Settings…", lambda: self.call_soon(self.open_settings)),
            item("Open revision notes", lambda: self.call_soon(self.open_notes)),
            pystray.Menu.SEPARATOR,
            item("Quit", lambda: self.call_soon(self.quit)),
        )
        self._tray = pystray.Icon(APP_NAME, tray_image(self.settings.buddy_color),
                                  f"{APP_NAME} {__version__}", menu)
        try:
            self._tray.run_detached()
        except Exception as e:
            print(f"[{APP_NAME}] tray icon disabled: {e}", file=sys.stderr)
            self._tray = None


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


def main() -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()  # all our windows are Toplevels
    root.title(APP_NAME)
    settings = Settings.load()
    app = App(root, settings)
    if not has_key(settings):
        root.after(500, app.open_settings)
    print(f"{APP_NAME} running. {settings.hotkey_ask} = ask, {settings.hotkey_toggle} = show/hide.")
    root.mainloop()
