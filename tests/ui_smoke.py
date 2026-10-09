"""Drive the real Tk windows with a fake Claude.

    xvfb-run -s "-screen 0 1600x900x24" python tests/ui_smoke.py [shot.png]
"""

import json
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
    pump(root, 0.3)
    sw = app._settings_win
    # The API key section is first, and the wheel scrolls even over a widget deep inside a card.
    first_card = sw.scroll.body.winfo_children()[0]
    assert "AI provider" in [w.cget("text") for w in first_card.winfo_children()[0].winfo_children()]
    assert sw.scroll.can_scroll(), "settings should be taller than its window (else this test proves nothing)"
    if sw.scroll.can_scroll():
        target = sw.scroll.body.winfo_children()[1].winfo_children()[-1]  # deep inside the 2nd card
        before = sw.scroll.canvas.yview()[0]
        target.event_generate("<MouseWheel>", delta=-120)
        pump(root, 0.1)
        assert sw.scroll.canvas.yview()[0] > before, "mouse wheel didn't scroll settings"
        sw.scroll.canvas.yview_moveto(1.0)
        pump(root, 0.1)
        assert sw.scroll.canvas.yview()[1] >= 0.999, "can't reach the bottom of settings"
        print("settings scroll OK")
    app._settings_win.mode.set("Hint — nudge me, no answer")
    app._settings_win._save()
    assert app.mode == "hint" and Settings.load().mode == "hint"

    b.close()
    pump(root, 0.1)
    assert b.state == "hidden"
    # --- quick trigger: look straight away (no prompt, no Enter), then type the suggestion -------------
    from fakes import SAMPLE

    payload = dict(SAMPLE, type_text="O(n^2)")
    fake = FakeClient(payload=payload)
    text = json.dumps(payload)
    fake.chunks = [text[i:i + 20] for i in range(0, len(text), 20)]
    app.tutor = Tutor(app.settings, client=fake)
    app.settings.instant = True
    partials = []
    orig_partial = b.show_partial
    b.show_partial = lambda f: (partials.append(f), orig_partial(f))
    app.on_trigger()
    for _ in range(300):
        pump(root, 0.02)
        if b.state == "showing" and not app.busy:
            break
    assert b.state == "showing", b.state  # never went through the "what are you stuck on?" prompt
    assert partials and partials[0].get("title"), partials
    assert b.type_box.winfo_ismapped() and "O(n^2)" in b.type_preview.cget("text")
    assert "Right Ctrl ×2" in b.footer.cget("text")

    import moodleclicky.typer as typer

    class FakeKeyboard:
        def __init__(self):
            self.log = []

        def pressed(self, key):
            log = self.log

            class Ctx:
                def __enter__(self):
                    log.append(("down", str(key)))

                def __exit__(self, *a):
                    log.append(("up", str(key)))

            return Ctx()

        def press(self, k):
            self.log.append(("press", k))

        def release(self, k):
            self.log.append(("release", k))

    kb = FakeKeyboard()
    real_type_into = typer.type_into
    typer.type_into = lambda root_, hwnd, txt, pause=lambda on: None: real_type_into(root_, hwnd, txt, pause, kb)
    root.clipboard_clear()
    root.clipboard_append("my old clipboard")
    app.on_trigger()  # second trigger while a suggestion is showing = type it
    pasted = root.clipboard_get()
    pump(root, 0.9)
    typer.type_into = real_type_into
    assert pasted == "O(n^2)", pasted
    assert ("press", "v") in kb.log and kb.log[0][0] == "down", kb.log  # Ctrl+V
    assert root.clipboard_get() == "my old clipboard"  # clipboard put back
    assert "Typed" in b.footer.cget("text") and not b.type_box.winfo_ismapped()
    b.close()

    root.destroy()
    print("ui_smoke OK")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
