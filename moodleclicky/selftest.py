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
    root.destroy()


def check_model(report: list[str]) -> None:
    import numpy as np

    from moodleclicky.lecture.audio import write_wav
    from moodleclicky.lecture.transcribe import WhisperTranscriber

    tmp = Path(tempfile.mkdtemp()) / "silence.wav"
    write_wav(tmp, np.zeros(16000, dtype=np.float32))
    WhisperTranscriber("tiny.en").transcribe(tmp)
    report.append("ok    speech model loads and runs (tiny.en)")


def run(args: list[str]) -> int:
    out = next((a for a in args if not a.startswith("--")), None)
    os.environ.setdefault("MOODLECLICKY_HOME", tempfile.mkdtemp(prefix="mc-selftest-"))
    report = [f"MoodleClicky self-test · python {sys.version.split()[0]} · frozen={getattr(sys, 'frozen', False)}"]
    ok = check_imports(report, set())
    for name, fn in (("ui", check_ui), ("model", check_model)):
        if name == "model" and "--with-model" not in args:
            continue
        try:
            fn(report)
        except Exception:
            ok = False
            report.append(f"FAIL  {name}:\n{traceback.format_exc()}")
    report.append("RESULT: " + ("PASS" if ok else "FAIL"))
    text = "\n".join(report)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    if sys.stdout:
        print(text)
    return 0 if ok else 1
