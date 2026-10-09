"""Clicky-style speech bubble: a small rounded bubble beside the cursor buddy whose text types itself out.

Clicks go straight through it (it never blocks what you're clicking). It plays the explanation one line at
a time - summary, each step (while the buddy flies to the thing it's talking about), the answer, why - and
then fades. The full card is still there via tray -> "Show full answer".
"""

from __future__ import annotations

import re
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass

from moodleclicky import theme as t
from moodleclicky.brain import Explanation
from moodleclicky.capture import monitor_bounds
from moodleclicky.winutil import IS_WIN, make_click_through

KEY = "#010204"  # transparent colour key (Windows) - outside the rounded shape
MAX_W = 300
MAX_CHARS = 280
PAD_X, PAD_Y, RADIUS = 14, 10, 14


@dataclass
class Line:
    text: str
    tag: str = ""  # small heading, e.g. "2 / 4" or "ANSWER"
    point: tuple[int, int] | None = None
    label: str = ""
    secs: float = 3.0
    hold: bool = False  # stay up until dismissed/timeout (e.g. the typing suggestion)


def plain(text: str) -> str:
    """Speech-friendly text: no code fences/markdown, shortened to a bubble-sized chunk."""
    text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(" ", 1)[0].rstrip(".,;:") + "…"
    return text


def reading_time(text: str) -> float:
    """Seconds to leave a line up: ~3 words/second plus a beat, clamped."""
    return max(2.6, min(12.0, 1.6 + len(text.split()) * 0.33))


def plan_lines(exp: Explanation, type_hint: str = "Right Ctrl ×2") -> list[Line]:
    if exp.error:
        return [Line(plain(exp.summary or exp.error), "HMM", secs=6.0)]
    lines = []
    if exp.summary:
        lines.append(Line(plain(exp.summary), exp.title[:40].upper() if exp.title else ""))
    n = len(exp.steps)
    for i, s in enumerate(exp.steps, 1):
        lines.append(Line(plain(s.text), f"{i} / {n}", s.point, s.label))
    if exp.answer:
        lines.append(Line(plain(exp.answer), "ANSWER"))
    if exp.why:
        lines.append(Line(plain(exp.why), "WHY"))
    for ln in lines:
        ln.secs = reading_time(ln.text)
    if exp.type_text:
        preview = exp.type_text.strip().splitlines()[0][:60] if exp.type_text.strip() else ""
        lines.append(Line(f"{type_hint} to type it:\n{preview}{'…' if len(exp.type_text) > len(preview) else ''}",
                          "✍ TYPE THIS", secs=25.0, hold=True))
    return lines


class SpeechBubble:
    def __init__(self, root: tk.Misc, anchor: Callable[[], tuple[int, int]], anchor_scale: Callable[[], float]):
        self.root = root
        self.anchor = anchor  # buddy tip position on screen
        self.anchor_scale = anchor_scale
        self.visible = False
        self._full = ""
        self._shown = 0
        self._tag = ""
        self._thinking = False
        self._phase = 0
        self._size = (MAX_W, 60)

        w = self.win = tk.Toplevel(root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        bg = KEY if IS_WIN else t.CARD
        if IS_WIN:
            w.config(bg=KEY)
            w.attributes("-transparentcolor", KEY)
        self.canvas = tk.Canvas(w, bg=bg, highlightthickness=0, width=MAX_W, height=60)
        self.canvas.pack(fill="both", expand=True)
        f = t.fonts(w)
        self.font, self.tag_font = f.body, f.tiny_bold
        w.withdraw()
        make_click_through(w)
        self._tick()

    # ---- public --------------------------------------------------------
    def say(self, text: str, tag: str = "", instant: bool = False) -> None:
        self._thinking = False
        self._full, self._tag = text, tag
        self._shown = len(text) if instant else 0
        self._show()

    def thinking(self, text: str = "Having a look") -> None:
        self._thinking = True
        self._full, self._tag, self._shown = text, "", len(text)
        self._show()

    def hide(self) -> None:
        self.visible = False
        self._thinking = False
        self.win.withdraw()

    @property
    def done_typing(self) -> bool:
        return self._shown >= len(self._full)

    # ---- internals -----------------------------------------------------
    def _show(self) -> None:
        if not self.visible:
            self.visible = True
            self.win.deiconify()
            self.win.attributes("-topmost", True)
        self._draw()

    def _tick(self) -> None:
        try:
            if self.visible:
                self._phase += 1
                if self._shown < len(self._full):
                    self._shown = min(len(self._full), self._shown + 3)  # ~90 chars/s typewriter
                self._draw()
                self._place()
            self.root.after(33, self._tick)
        except tk.TclError:
            pass

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        text = self._full[: self._shown]
        if self._thinking:
            text += "." * (1 + (self._phase // 8) % 3)
        y = PAD_Y
        tag_h = 0
        if self._tag:
            tid = c.create_text(PAD_X + 6, y, text=self._tag, anchor="nw", fill=t.ACCENT_HI, font=self.tag_font)
            tag_h = c.bbox(tid)[3] - c.bbox(tid)[1] + 3
        body = c.create_text(PAD_X + 6, y + tag_h, text=text or " ", anchor="nw", fill=t.INK, font=self.font,
                             width=MAX_W - 2 * PAD_X - 6)
        # size to the *full* text so the bubble doesn't jitter while typing
        probe = c.create_text(0, 0, text=self._full or " ", anchor="nw", font=self.font, width=MAX_W - 2 * PAD_X - 6)
        bx = c.bbox(probe)
        c.delete(probe)
        tw = max(80, min(MAX_W - 2 * PAD_X - 6, bx[2] - bx[0]))
        if self._tag:
            tw = max(tw, c.bbox(tid)[2] - c.bbox(tid)[0])
        w = int(tw + 2 * PAD_X + 6)
        h = int(tag_h + (bx[3] - bx[1]) + 2 * PAD_Y)
        shape = t.rounded_points(7, 1, w - 1, h - 1, RADIUS, tail=("left", 16, 12, 6))  # tail points at the buddy
        bubble = c.create_polygon(shape, fill=t.CARD, outline=t.BORDER_HI)
        c.tag_lower(bubble)
        c.tag_raise(body)
        self._size = (w, h)
        c.config(width=w, height=h)

    def _place(self) -> None:
        ax, ay = self.anchor()
        k = self.anchor_scale()
        w, h = self._size
        left, top, right, bottom = monitor_bounds(ax, ay)
        x, y = ax + int(36 * k), ay + int(8 * k)
        if x + w > right - 6:  # flip to the left of the buddy near the screen edge
            x = ax - w - 14
        y = max(top + 6, min(y, bottom - h - 6))
        self.win.geometry(f"{w}x{h}+{int(x)}+{int(y)}")


class SpeechPlayer:
    """Plays a list of Lines: says each one, points the buddy, waits, moves on; then fades away."""

    def __init__(self, root: tk.Misc, bubble: SpeechBubble, point: Callable[[tuple[int, int] | None, str], None],
                 on_finish: Callable[[], None]):
        self.root, self.bubble, self.point, self.on_finish = root, bubble, point, on_finish
        self.lines: list[Line] = []
        self.idx = -1
        self._job = None

    @property
    def playing(self) -> bool:
        return self._job is not None

    def play(self, lines: list[Line]) -> None:
        self.stop(quiet=True)
        self.lines, self.idx = lines, -1
        self._next()

    def stop(self, quiet: bool = False) -> None:
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None
        if not quiet:
            self.bubble.hide()
            self.point(None, "")
            self.on_finish()

    def _next(self) -> None:
        self.idx += 1
        if self.idx >= len(self.lines):
            self._job = self.root.after(3500, self.stop)  # linger a moment, then fade
            return
        ln = self.lines[self.idx]
        self.point(ln.point, ln.label)
        self.bubble.say(ln.text, ln.tag)
        type_secs = len(ln.text) / 90
        if ln.hold:
            self._job = self.root.after(int((ln.secs + type_secs) * 1000), self.stop)
        else:
            self._job = self.root.after(int((ln.secs + type_secs) * 1000), self._next)
