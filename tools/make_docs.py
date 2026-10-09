"""Render the README screenshots + demo GIF over a mock quiz page (no API calls).

    xvfb-run -s "-screen 0 1600x900x24" python tools/make_docs.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ["MOODLECLICKY_HOME"] = tempfile.mkdtemp()

import tkinter as tk

import mss
from PIL import Image

from fakes import FakeClient
from moodleclicky.app import App
from moodleclicky.brain import Tutor
from moodleclicky.config import Settings

DOCS = ROOT / "docs"
CODE = [
    "def count_pairs(items):",
    "    total = 0",
    "    for a in items:",
    "        for b in items:",
    "            if a < b:",
    "                total += 1",
    "    return total",
]
CODE_Y0, LINE_H = 262, 28
OPTS = ["a. O(n)", "b. O(n log n)", "c. O(n²)", "d. O(2ⁿ)"]
OPT_Y0, OPT_H = 506, 40


def line_y(i: int) -> int:
    return CODE_Y0 + i * LINE_H


BREAKDOWN = {
    "title": "Q3 - Big-O of count_pairs",
    "summary": "How does the amount of work grow as the list `items` gets bigger? That growth rate is the Big-O.",
    "steps": [
        {"text": "The outer loop `for a in items` runs once per item, so n times.",
         "label": "outer loop", "x": 372, "y": line_y(2)},
        {"text": "For EACH of those passes, the inner loop `for b in items` runs n times again.",
         "label": "inner loop", "x": 412, "y": line_y(3)},
        {"text": "The `if` and `total += 1` are constant work, O(1). They don't change how it grows.",
         "label": "constant work", "x": 452, "y": line_y(4)},
        {"text": "Total work is about n x n = n². Drop the constants and you get O(n²), which is option c.",
         "label": "option c", "x": 352, "y": OPT_Y0 + 2 * OPT_H},
    ],
    "answer": "c. O(n²)\n\nTwo loops over the same list, one inside the other:\n```python\n"
              "for a in items:      # n times\n    for b in items:  # n times each\n"
              "        ...          # O(1)\n```\nn × n = n² steps.",
    "why": "Loops one after another ADD (n + n is still O(n)). Loops nested inside each other MULTIPLY "
           "(n × n = O(n²)). Constant work inside a loop never changes the Big-O.",
    "check_yourself": "If the inner loop were `for b in items[:10]:`, what would the Big-O be?",
}

HINT = {
    "title": "Q3 - a nudge, not the answer",
    "summary": "Think about how many times the innermost line runs when the list has n items.",
    "steps": [
        {"text": "Count how many times this loop runs for a list of 5 items.", "label": "start here",
         "x": 372, "y": line_y(2)},
        {"text": "Now: for ONE pass of the outer loop, how many times does this one run?",
         "label": "and this?", "x": 412, "y": line_y(3)},
        {"text": "Multiply your two answers. Which option grows like that?", "label": "", "x": -1, "y": -1},
    ],
    "answer": "",
    "why": "Nested loops multiply their counts.",
    "check_yourself": "What would change if the loops were one after the other instead?",
}


class SlowFake(FakeClient):
    def _stream(self, **kw):
        time.sleep(1.2)
        return super()._stream(**kw)


def mock_quiz(root: tk.Tk) -> tk.Toplevel:
    page = tk.Toplevel(root)
    page.overrideredirect(True)
    page.geometry("1600x900+0+0")
    c = tk.Canvas(page, width=1600, height=900, bg="white", highlightthickness=0)
    c.pack()
    c.create_rectangle(0, 0, 1600, 56, fill="#1f2a44", outline="")
    c.create_text(24, 28, anchor="w", fill="white", font=("DejaVu Sans", 14, "bold"), text="My Uni Learn")
    c.create_text(200, 28, anchor="w", fill="#c9d3ea", font=("DejaVu Sans", 12),
                  text="COMP1234 Algorithms  ›  Week 4  ›  Quiz 3: Complexity")
    c.create_rectangle(0, 56, 260, 900, fill="#f4f5f7", outline="")
    c.create_text(24, 90, anchor="w", font=("DejaVu Sans", 12, "bold"), fill="#333", text="Quiz navigation")
    for i in range(6):
        x = 24 + (i % 4) * 52
        y = 120 + (i // 4) * 52
        c.create_rectangle(x, y, x + 40, y + 40, outline="#999", fill="#dfe8f7" if i == 2 else "white")
        c.create_text(x + 20, y + 20, text=str(i + 1), font=("DejaVu Sans", 11))
    c.create_rectangle(300, 86, 1320, 720, outline="#d0d4db", fill="white")
    c.create_rectangle(300, 86, 470, 160, outline="#d0d4db", fill="#f4f5f7")
    c.create_text(316, 106, anchor="w", font=("DejaVu Sans", 12, "bold"), text="Question 3")
    c.create_text(316, 130, anchor="w", font=("DejaVu Sans", 9), fill="#666", text="Not yet answered")
    c.create_text(316, 147, anchor="w", font=("DejaVu Sans", 9), fill="#666", text="Marked out of 2.00")
    c.create_text(500, 120, anchor="w", font=("DejaVu Sans", 13),
                  text="What is the worst-case time complexity of the function below?")
    c.create_rectangle(340, CODE_Y0 - 28, 1000, line_y(len(CODE) - 1) + 24, fill="#f6f8fa", outline="#e1e4e8")
    for i, line in enumerate(CODE):
        c.create_text(360, line_y(i), anchor="w", font=("DejaVu Sans Mono", 13), fill="#24292e", text=line)
    c.create_text(340, OPT_Y0 - 34, anchor="w", font=("DejaVu Sans", 11), fill="#444", text="Select one:")
    for i, opt in enumerate(OPTS):
        y = OPT_Y0 + i * OPT_H
        c.create_oval(342, y - 8, 358, y + 8, outline="#666", width=2)
        c.create_text(372, y, anchor="w", font=("DejaVu Sans", 13), text=opt)
    c.create_rectangle(340, 664, 420, 698, fill="#0f6cbf", outline="")
    c.create_text(380, 681, text="Check", fill="white", font=("DejaVu Sans", 11, "bold"))
    c.create_rectangle(1200, 740, 1320, 776, fill="#0f6cbf", outline="")
    c.create_text(1260, 758, text="Next page", fill="white", font=("DejaVu Sans", 11, "bold"))
    return page


class Director:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.page = mock_quiz(self.root)
        self.sct = (getattr(mss, "MSS", None) or mss.mss)()
        self.frames: list[Image.Image] = []

    def pump(self, secs: float, record: bool = False) -> None:
        end = time.time() + secs
        while time.time() < end:
            self.root.update()
            if record:
                self.frame()
            time.sleep(0.03)

    def frame(self) -> None:
        raw = self.sct.grab(self.sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        self.frames.append(img.resize((800, 450), Image.LANCZOS))

    def snap(self, name: str, crop=None) -> None:
        self.pump(0.6)
        raw = self.sct.grab(self.sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        if crop:
            img = img.crop(crop)
        img.save(DOCS / name, optimize=True)
        print("wrote", name)

    def move(self, x: int, y: int, steps: int = 1, record: bool = False) -> None:
        px, py = self.root.winfo_pointerxy()
        for i in range(1, steps + 1):
            self.page.event_generate("<Motion>", warp=True, x=int(px + (x - px) * i / steps),
                                     y=int(py + (y - py) * i / steps))
            self.pump(0.03, record)

    def wait_speech(self, app: App, record: bool = False) -> None:
        for _ in range(400):
            self.pump(0.03, record)
            if not app.busy and app.player.playing:
                return
        raise RuntimeError("no speech")

    def wait_result(self, app: App, record: bool = False) -> None:
        for _ in range(400):
            self.pump(0.03, record)
            if app.bubble.state == "showing" and not app.busy:
                return
        raise RuntimeError("no result")


def make_app(d: Director, payload, mode: str, slow: bool = False) -> App:
    s = Settings(mode=mode, max_image_edge=1600)
    client = SlowFake(payload) if slow else FakeClient(payload)
    app = App(d.root, s, tutor=Tutor(s, client=client), enable_hotkeys=False, enable_tray=False)
    # Xvfb has no transparency or always-on-top: tint the buddy's box like the code panel
    # and keep the mock page at the bottom of the stack.
    app.buddy.canvas.config(bg="#f6f8fa")
    d.root.update()
    d.page.lower()
    return app


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    d = Director()

    # --- demo GIF: follow -> double-tap Right Ctrl -> speech bubble talks it through ----------
    import moodleclicky.speech as speech

    speech.reading_time = lambda text: 1.7  # brisker pauses so the GIF stays short
    app = make_app(d, dict(BREAKDOWN, type_text="c. O(n²)"), "breakdown", slow=True)
    d.move(1150, 760)
    d.pump(0.4)
    d.move(560, 420, steps=30, record=True)
    d.pump(0.5, record=True)
    app.on_trigger()  # what a double-tap of Right Ctrl does
    d.wait_speech(app, record=True)
    stills = {}
    for _ in range(900):
        d.pump(0.05, record=True)
        if app.player.idx == 2 and "pointing" not in stills:
            d.pump(1.0, record=True)
            stills["pointing"] = True
            d.snap("pointing.png")
        if not app.player.playing:
            break
    frames = d.frames[::3]
    frames[0].save(DOCS / "demo.gif", save_all=True, append_images=frames[1:], duration=90, loop=0, optimize=True)
    print("wrote demo.gif", len(frames), "frames")

    # --- the full card (tray -> Show full answer, or Ctrl+Alt+Space) ------------------
    app.show_full_answer()
    app.bubble.jump_answer()
    d.snap("answer.png")
    app.bubble.close()

    app.start_prompt()
    d.snap("prompt.png")
    app.bubble.close()
    app.buddy.win.destroy()
    app.bubble.win.destroy()
    app.speech.win.destroy()

    happ = make_app(d, HINT, "hint")
    happ.settings.compact = False  # show the hint in the full card for the README
    d.move(560, 420)
    happ.ask("")
    d.wait_result(happ)
    happ.bubble.next()
    d.snap("hint.png")
    happ.bubble.close()

    happ.open_settings()
    d.pump(0.5)
    sw = happ._settings_win.win
    sw.geometry("+560+40")
    d.pump(0.5)
    sw.update_idletasks()
    x, y, w, h = sw.winfo_rootx(), sw.winfo_rooty(), sw.winfo_width(), sw.winfo_height()
    d.snap("settings.png", crop=(x - 2, y - 2, x + w + 2, y + h + 2))
    sw.destroy()
    notetaker_shots(d, happ)
    d.root.destroy()


MEETING_LINES = [
    "Okay so the deadline for the group report is the twenty-first.",
    "I think we should split it into four sections, one each.",
    "Priya, can you take the literature review?",
    "Sure. Dom, could you do the database design and the ER diagram?",
    "We also need someone to book the presentation slot.",
    "Let's meet again Thursday at six to merge everything.",
]
MEETING_NOTES = {
    "title": "Group project - kick-off",
    "tl_dr": "Report due on the 21st. Work split four ways; next sync Thursday 6pm.",
    "decisions": ["Split the report into four sections, one per person", "Meet Thursday 6pm to merge"],
    "action_items": [{"who": "Priya", "task": "Literature review", "due": "Thu"},
                     {"who": "Dom", "task": "Database design + ER diagram", "due": "Thu"},
                     {"who": "Unassigned", "task": "Book the presentation slot", "due": ""}],
    "my_tasks": ["Database design + ER diagram (by Thursday)", "Offer to book the presentation slot"],
    "plan": [{"step": "Draft own section", "owner": "Everyone", "when": "by Thu"},
             {"step": "Merge + edit at Thursday meeting", "owner": "Everyone", "when": "Thu 6pm"},
             {"step": "Final proofread and submit", "owner": "Priya", "when": "by the 21st"}],
    "open_questions": ["Who books the presentation slot?"],
    "risks": ["Only one sync before the deadline"],
}


def notetaker_shots(d: Director, app: App) -> None:
    import numpy as np

    from moodleclicky.brain import Reply
    from moodleclicky.lecture import summarise
    from moodleclicky.lecture.audio import write_wav
    from moodleclicky.lecture.session import Session
    from moodleclicky.lecture.transcribe import Segment
    from moodleclicky.lecture_ui import NotesViewer, NotetakerWindow

    class Rec:
        def __init__(self, folder, on_chunk):
            self.folder, self.on_chunk, self.recorded_secs, self.level = Path(folder), on_chunk, 0.0, 0.42
            self.folder.mkdir(parents=True, exist_ok=True)

        def start(self):
            for i in range(len(MEETING_LINES)):
                p = self.folder / f"chunk_{i:04d}.wav"
                write_wav(p, np.zeros(1600, dtype=np.float32))
                self.on_chunk(p, i * 41.0)
            self.recorded_secs = 1012

        def status(self):
            return "mic: ok · computer audio: ok"

        def pause(self):
            pass

        def resume(self):
            pass

        def stop(self):
            pass

    class Tx:
        def transcribe(self, wav, offset, prompt=""):
            return [Segment(offset, offset + 8, MEETING_LINES[int(offset // 41)])]

    class Backend:
        def chat(self, settings, system, history, schema):
            return Reply(json.dumps(MEETING_NOTES), None, 0.004, "end")

    summarise.make_backend = lambda settings: Backend()
    app.settings.your_name = "Dom"
    nt = NotetakerWindow(d.root, app.settings, app.call_soon, lambda p: None,
                         session_factory=lambda st, kind, on_update: Session(
                             st, kind, recorder_factory=Rec, transcriber=Tx(), on_update=on_update))
    nt.win.geometry("460x760+80+60")
    nt.kind.set("meeting")
    nt.start()
    for _ in range(100):
        d.pump(0.03)
        if len(nt.session.segments) == len(MEETING_LINES):
            break
    nt.session.mark()
    nt.refresh()
    d.pump(0.5)
    nt.win.update_idletasks()
    x, y, w, h = nt.win.winfo_rootx(), nt.win.winfo_rooty(), nt.win.winfo_width(), nt.win.winfo_height()
    d.snap("notetaker.png", crop=(x - 2, y - 2, x + w + 2, y + h + 2))
    md = summarise.notes_markdown("meeting", MEETING_NOTES, "Thu 09 Oct 2026, 14:05", "16:52")
    v = NotesViewer(d.root, MEETING_NOTES["title"], md, on_open=lambda: None)
    v.win.geometry("560x640+560+60")
    d.pump(0.5)
    v.win.update_idletasks()
    x, y, w, h = v.win.winfo_rootx(), v.win.winfo_rooty(), v.win.winfo_width(), v.win.winfo_height()
    d.snap("meeting_notes.png", crop=(x - 2, y - 2, x + w + 2, y + h + 2))
    nt.session.stop()
    nt.session.wait(5)


if __name__ == "__main__":
    main()
