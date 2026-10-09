"""Offline self-test: `MoodleClicky.exe --selftest [report.txt] [--with-model]`.

Checks every dependency imports (catches a broken .exe build), then drives the real windows with a
fake AI: hotkey prompt -> screenshot -> breakdown -> buddy points -> answer, and the notetaker:
record -> transcript -> catch up -> notes. Exit code 0 = all good. No API calls, no microphone needed.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

MODULES = ["anthropic", "mss", "PIL", "pynput", "pystray", "keyring", "numpy", "faster_whisper", "ctranslate2",
           "soundcard"]

SAMPLE = {
    "title": "Self-test", "summary": "Checking the pop-up works.",
    "steps": [{"text": "Point here.", "label": "here", "x": 100, "y": 100},
              {"text": "No target.", "label": "", "x": -1, "y": -1}],
    "answer": "42\n```python\nprint(42)\n```", "why": "Because.", "check_yourself": "Why 42?",
}


class _Stream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


class FakeClaude:
    def __init__(self):
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kw):
        return _Stream(SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(SAMPLE))], stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=10, output_tokens=10, cache_creation_input_tokens=0,
                                  cache_read_input_tokens=0)))


def check(ok: bool, msg: str = "check failed") -> None:
    """Like assert, but survives `python -O` / optimised builds."""
    if not ok:
        raise RuntimeError(msg)


def check_imports(report: list[str], skip: set[str]) -> bool:
    ok = True
    for name in MODULES:
        if name in skip:
            continue
        try:
            __import__(name)
            report.append(f"ok    import {name}")
        except Exception as e:
            # Tray/audio backends are only guaranteed on Windows (Linux CI has no Gtk/PulseAudio).
            fatal = sys.platform == "win32" or name not in ("soundcard", "pystray")
            ok = ok and not fatal
            report.append(f"{'FAIL' if fatal else 'warn'}  import {name}: {type(e).__name__}: {e}")
    return ok


def pump(root, secs: float) -> None:
    end = time.time() + secs
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def check_ui(report: list[str]) -> None:
    import tkinter as tk

    import numpy as np

    from moodleclicky.app import App
    from moodleclicky.brain import Reply, Tutor
    from moodleclicky.config import Settings
    from moodleclicky.lecture.audio import write_wav
    from moodleclicky.lecture.session import Session
    from moodleclicky.lecture.transcribe import Segment

    root = tk.Tk()
    root.withdraw()
    s = Settings()
    app = App(root, s, tutor=Tutor(s, client=FakeClaude()), enable_hotkeys=False, enable_tray=False)
    pump(root, 0.2)
    app.start_prompt()
    pump(root, 0.2)
    check(app.bubble.state == "prompt", app.bubble.state)
    app.bubble._submit()  # real screenshot of the real screen
    for _ in range(500):
        pump(root, 0.02)
        if app.bubble.state == "showing" and not app.busy:
            break
    check(app.bubble.state == "showing" and not app.bubble.pages[0].text.startswith("Couldn't"),
          app.bubble.pages[0].text)
    app.bubble.next()
    pump(root, 0.8)
    check(app.buddy.target_point is not None)
    app.bubble.jump_answer()
    check(app.bubble.current().kind == "answer")
    app.bubble.close()
    report.append("ok    hotkey -> screenshot -> breakdown -> buddy points -> answer")

    app.look_now()  # what a double-tap of Right Ctrl does: speech bubble, no card
    for _ in range(500):
        pump(root, 0.02)
        if not app.busy and app.player.playing:
            break
    check(app.player.playing and app.speech.visible and app.bubble.state == "hidden",
          f"speech bubble didn't play (playing={app.player.playing}, card={app.bubble.state})")
    pump(root, 0.5)
    w = app.speech.win.winfo_width()
    check(60 <= w <= 330, f"speech bubble is {w}px wide")
    app.dismiss()
    check(not app.speech.visible, "Esc didn't hide the speech bubble")
    report.append("ok    double-tap -> speech bubble talks it through (small, click-through), Esc hides")

    class Rec:
        def __init__(self, folder, on_chunk):
            self.folder, self.on_chunk, self.recorded_secs, self.level = Path(folder), on_chunk, 0.0, 0.0
            self.folder.mkdir(parents=True, exist_ok=True)

        def start(self):
            for i in range(2):
                p = self.folder / f"chunk_{i:04d}.wav"
                write_wav(p, np.zeros(1600, dtype=np.float32))
                self.recorded_secs += 30
                self.on_chunk(p, i * 30.0)

        def status(self):
            return "fake"

        def pause(self):
            pass

        def resume(self):
            pass

        def stop(self):
            pass

    class Tx:
        def transcribe(self, wav, offset, prompt=""):
            return [Segment(offset, offset + 5, f"Line at {int(offset)} seconds.")]

    notes_json = {"title": "Self-test lecture", "tl_dr": "ok", "key_points": ["a"], "concepts": [],
                  "examples": [], "marked_moments": [], "to_do": [], "questions_to_review": []}

    class Backend:
        name = "anthropic"

        def chat(self, settings, system, history, schema):
            if "now_discussing" in schema["properties"]:
                return Reply(json.dumps({"now_discussing": "x", "what_you_missed": ["y"], "for_you": [],
                                         "say_this": ""}), None, 0.0, "end")
            return Reply(json.dumps(notes_json), None, 0.0, "end")

    import moodleclicky.lecture.summarise as summ

    summ.make_backend = lambda settings: Backend()
    app._notetaker = None
    from moodleclicky import lecture_ui

    app._notetaker = lecture_ui.NotetakerWindow(
        root, s, app.call_soon, lambda p: None,
        session_factory=lambda st, kind, on_update: Session(st, kind, recorder_factory=Rec, transcriber=Tx(),
                                                            on_update=on_update))
    nt = app._notetaker
    nt.start()
    pump(root, 0.5)
    nt.mark()
    nt.stop()
    check(nt.session.wait(10), "transcriber didn't finish")
    pump(root, 0.3)
    check(len(nt.session.segments) == 2)
    nt.catch_up()
    for _ in range(300):
        pump(root, 0.02)
        if not nt.busy:
            break
    nt.make_notes()
    for _ in range(300):
        pump(root, 0.02)
        if not nt.busy:
            break
    check((nt.session.folder / "notes.md").exists(), nt.status.cget("text"))
    report.append("ok    notetaker: record -> transcript -> catch up -> notes.md")

    app.open_settings()
    pump(root, 0.3)
    app._settings_win._save()
    report.append("ok    settings window opens and saves")
    if sys.platform == "win32":
        report.append("...   keyboard checks (real key events)")
        check_keyboard(root, report)
    root.destroy()


def check_keyboard(root, report: list[str]) -> None:
    """Real key events (Windows): double-tap Ctrl wakes the buddy; a suggestion is pasted into a text box."""
    import tkinter as tk

    from pynput.keyboard import Controller, Key

    from moodleclicky.triggers import KeyTrigger
    from moodleclicky.typer import type_into
    from moodleclicky.winutil import foreground_window

    kb = Controller()
    fired = []
    trig = KeyTrigger("double_rctrl", lambda: fired.append(1))
    trig.start()
    time.sleep(0.5)
    def double_tap(key):
        for _ in range(2):
            kb.press(key)
            time.sleep(0.05)
            kb.release(key)
            time.sleep(0.12)
        time.sleep(0.6)

    with kb.pressed(Key.ctrl_r):  # Ctrl used with another key (Ctrl+Shift here - harmless) must NOT trigger
        kb.press(Key.shift)
        kb.release(Key.shift)
    time.sleep(0.6)
    double_tap(Key.ctrl_l)  # Left Ctrl x2 is PowerToys Find My Mouse - must NOT trigger
    double_tap(Key.ctrl_r)  # Right Ctrl x2 = wake up
    trig.stop()
    check(fired == [1], f"double-tap Right Ctrl fired {len(fired)} times (want 1)")
    report.append("ok    double-tap Right Ctrl wakes the buddy (Left Ctrl x2 and Ctrl+other key don't)")

    win = tk.Toplevel(root)
    win.title("MoodleClicky self-test box")
    entry = tk.Entry(win, width=40)
    entry.pack(padx=20, pady=20)
    win.deiconify()
    win.lift()
    win.focus_force()
    entry.focus_set()
    pump(root, 0.6)
    hwnd = foreground_window()
    type_into(root, hwnd, "O(n^2) because the loops nest")
    pump(root, 1.0)
    got = entry.get()
    win.destroy()
    check(got == "O(n^2) because the loops nest", f"typed text was {got!r}")
    report.append("ok    suggestion pasted into a real text box")


def check_model(report: list[str]) -> None:
    import numpy as np

    from moodleclicky.lecture.audio import write_wav
    from moodleclicky.lecture.transcribe import WhisperTranscriber

    tmp = Path(tempfile.mkdtemp()) / "silence.wav"
    write_wav(tmp, np.zeros(16000, dtype=np.float32))
    WhisperTranscriber("tiny.en").transcribe(tmp)
    report.append("ok    speech model loads and runs (tiny.en)")


class Report(list):
    """Lines are printed and saved as they happen, so a hang or crash still shows how far it got."""

    def __init__(self, out: str | None):
        super().__init__()
        self.out = out

    def append(self, line: str) -> None:
        super().append(line)
        if sys.stdout:
            print(line, flush=True)
        if self.out:
            try:
                Path(self.out).write_text("\n".join(self), encoding="utf-8")
            except OSError:
                pass


def run(args: list[str]) -> int:
    import threading

    out = next((a for a in args if not a.startswith("--")), None)
    os.environ.setdefault("MOODLECLICKY_HOME", tempfile.mkdtemp(prefix="mc-selftest-"))
    report = Report(out)
    report.append(f"MoodleClicky self-test · python {sys.version.split()[0]} · frozen={getattr(sys, 'frozen', False)}")

    def watchdog():  # never hang a build: give up loudly
        report.append("RESULT: FAIL (self-test timed out - the last 'ok' line above shows how far it got)")
        os._exit(3)

    timer = threading.Timer(600 if "--with-model" in args else 240, watchdog)
    timer.daemon = True
    timer.start()
    ok = check_imports(report, set())
    for name, fn in (("ui", check_ui), ("model", check_model)):
        if name == "model" and "--with-model" not in args:
            continue
        try:
            fn(report)
        except BaseException:  # incl. KeyboardInterrupt from a stray Ctrl+C in a console
            ok = False
            report.append(f"FAIL  {name}:\n{traceback.format_exc()}")
    timer.cancel()
    report.append("RESULT: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1
