"""Drive the real Tk windows with a fake Claude.

    xvfb-run -s "-screen 0 1600x900x24" python tests/ui_smoke.py [shot.png]
"""

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["MOODLECLICKY_HOME"] = tempfile.mkdtemp()

import tkinter as tk

from PIL import Image

from fakes import FakeClient
from moodleclicky import capture
from moodleclicky.app import App
from moodleclicky.brain import Tutor
from moodleclicky.config import Settings

capture.grab = lambda cursor, max_edge=1568: capture.build_shot(
    Image.new("RGB", (1600, 900), "white"), 0, 0, cursor, max_edge)


def pump(root, secs):
    end = time.time() + secs
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def main(out=None):
    root = tk.Tk()
    root.withdraw()
    s = Settings()
    app = App(root, s, tutor=Tutor(s, client=FakeClient()), enable_hotkeys=False, enable_tray=False)
    pump(root, 0.3)

    app.start_prompt()
    pump(root, 0.2)
    assert app.bubble.state == "prompt", app.bubble.state
    app.bubble.entry.insert(0, "what is the big-O here?")
    app.bubble._submit()
    for _ in range(300):
        pump(root, 0.02)
        if app.bubble.state == "showing":
            break
    assert app.bubble.state == "showing", app.bubble.state
    b = app.bubble
    assert b.current().kind == "summary" and len(b.pages) == 7, [p.kind for p in b.pages]

    b.next()
    pump(root, 1.2)
    want = app.tutor.shot.to_screen(200, 150)
    assert app.buddy.target_point == want, (app.buddy.target_point, want)
    tip = app.buddy.position()
    assert abs(tip[0] - want[0]) < 6 and abs(tip[1] - want[1]) < 6, tip  # buddy flew to the target
    if out:
        os.system(f"import -window root {out}")  # nosec B605 - test helper, ImageMagick

    b.jump_answer()
    pump(root, 0.1)
    assert b.current().kind == "answer" and app.buddy.target_point is None
    assert "range(n)" in b.body.get("1.0", "end")

    b.entry.insert(0, "why squared?")
    b._submit()
    for _ in range(300):
        pump(root, 0.02)
        if not app.busy:
            break
    assert len(app.tutor.history) == 4

    app.toggle_buddy()
    assert not app.buddy.visible
    app.toggle_buddy()
    assert app.buddy.visible

    app.open_settings()
    pump(root, 0.2)
    app._settings_win.mode.set("Hint — nudge me, no answer")
    app._settings_win._save()
    assert app.mode == "hint" and Settings.load().mode == "hint"

    b.close()
    pump(root, 0.1)
    assert b.state == "hidden"
    root.destroy()
    print("ui_smoke OK")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
