"""The Clippy-style pop-up: one idea per page, Back/Next, show-answer, follow-up questions."""

from __future__ import annotations

import re
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass

from moodleclicky import theme as t
from moodleclicky.brain import Explanation
from moodleclicky.capture import monitor_bounds
from moodleclicky.config import MODES

MODE_NAMES = {"breakdown": "Breakdown", "hint": "Hint", "check": "Check"}

WIDTH = 410


@dataclass
class Page:
    kind: str  # summary | step | answer | why | check
    heading: str
    text: str
    point: tuple[int, int] | None = None
    label: str = ""


def build_pages(exp: Explanation) -> list[Page]:
    pages = [Page("summary", "What it's asking", exp.summary or "Let's take a look.")]
    n = len(exp.steps)
    for i, s in enumerate(exp.steps, 1):
        pages.append(Page("step", f"Step {i} of {n}", s.text, s.point, s.label))
    if exp.answer:
        pages.append(Page("answer", "Answer", exp.answer))
    if exp.why:
        pages.append(Page("why", "Why it works", exp.why))
    if exp.check_yourself:
        pages.append(Page("check", "Check yourself", exp.check_yourself))
    return pages


def split_code(text: str) -> list[tuple[str, bool]]:
    """Split on ``` fences -> [(chunk, is_code)]. The language tag after a fence is dropped."""
    parts = text.split("```")
    out = []
    for i, part in enumerate(parts):
        code = i % 2 == 1
        if code and "\n" in part:
            first, rest = part.split("\n", 1)
            if first.strip() and " " not in first.strip():
                part = rest
        part = part.strip("\n")
        if part:
            out.append((part, code))
    return out


class Bubble:
    def __init__(
        self,
        root: tk.Tk,
        on_ask: Callable[[str], None],
        on_follow_up: Callable[[str], None],
        on_settings: Callable[[], None],
        on_page: Callable[[Page | None], None],
        on_close: Callable[[], None],
        get_mode: Callable[[], str],
        set_mode: Callable[[str], None],
        on_type: Callable[[], None] | None = None,
        type_hint: str = "Ctrl Ctrl",
    ):
        self.root = root
        self.on_type = on_type or (lambda: None)
        self.type_text = ""
        self.on_ask, self.on_follow_up = on_ask, on_follow_up
        self.on_settings, self.on_page, self.on_close = on_settings, on_page, on_close
        self.get_mode, self.set_mode = get_mode, set_mode
        self.pages: list[Page] = []
        self.idx = 0
        self.state = "hidden"  # hidden | prompt | thinking | showing
        self._drag = (0, 0)
        self._anchor: tuple[tuple[int, int], bool] | None = None

        w = self.win = tk.Toplevel(root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.config(bg=t.BORDER)
        t.style_ttk(w)
        f = self.f = t.fonts(w)
        inner = self.inner = tk.Frame(w, bg=t.CARD, padx=16, pady=14)
        inner.pack(padx=1, pady=1, fill="both", expand=True)

        # header: accent dot · title · ⚙ ✕  (drag to move)
        head = tk.Frame(inner, bg=t.CARD)
        head.pack(fill="x")
        self.dot = tk.Canvas(head, width=10, height=10, bg=t.CARD, highlightthickness=0)
        self.dot.create_oval(1, 1, 9, 9, fill=t.ACCENT, outline="")
        self.dot.pack(side="left", padx=(0, 8), pady=(6, 0), anchor="n")
        self.title = tk.Label(head, text="MoodleClicky", bg=t.CARD, fg=t.INK, font=f.title, anchor="w",
                              wraplength=WIDTH - 110, justify="left")
        self.title.pack(side="left", fill="x", expand=True)
        t.PillButton(head, "✕", self.close, kind="icon", tooltip="Close (Esc)").pack(side="right")
        t.PillButton(head, "⚙", self.on_settings, kind="icon", tooltip="Settings").pack(side="right", padx=(0, 2))
        for wdg in (head, self.title):
            wdg.bind("<ButtonPress-1>", self._drag_start)
            wdg.bind("<B1-Motion>", self._drag_move)

        self.mode_var = tk.StringVar(w, get_mode())
        self.modes = t.Segmented(inner, [(m, MODE_NAMES[m]) for m in MODES], variable=self.mode_var,
                                 command=self._pick_mode, height=28, width=270)
        self.modes.pack(anchor="w", pady=(12, 10))

        # "✍ Type this" card: text the buddy can paste into the box you were typing in
        tb = self.type_box = tk.Frame(inner, bg=t.CODE_BG, padx=12, pady=9)
        trow = tk.Frame(tb, bg=t.CODE_BG)
        trow.pack(fill="x")
        tk.Label(trow, text="✍  TYPE THIS", bg=t.CODE_BG, fg=t.SUCCESS, font=f.tiny_bold).pack(side="left")
        self.type_btn = t.PillButton(trow, f"Type it  ·  {type_hint}", lambda: self.on_type(), kind="primary",
                                     height=26, bg=t.CODE_BG)
        self.type_btn.pack(side="right")
        self.type_preview = tk.Label(tb, text="", bg=t.CODE_BG, fg=t.CODE_INK, font=f.mono, anchor="w",
                                     justify="left", wraplength=WIDTH - 60)
        self.type_preview.pack(fill="x", pady=(6, 0))

        # "STEP 2 OF 5" + progress dots
        hrow = self.hrow = tk.Frame(inner, bg=t.CARD)
        hrow.pack(fill="x")
        self.heading = tk.Label(hrow, text="", bg=t.CARD, fg=t.ACCENT_HI, font=f.tiny_bold, anchor="w")
        self.heading.pack(side="left")
        self.progress = tk.Canvas(hrow, height=8, width=120, bg=t.CARD, highlightthickness=0)
        self.progress.pack(side="right")

        # The text sits in a fixed-pixel box so the pop-up hugs its content exactly.
        self.body_box = tk.Frame(inner, bg=t.CARD, width=WIDTH - 34, height=60)
        self.body_box.pack_propagate(False)
        self.body = tk.Text(self.body_box, width=44, height=4, wrap="word", cursor="arrow")
        t.style_text(self.body, bg=t.CARD)
        self.body.pack(fill="both", expand=True)
        self.body_box.pack(fill="x", pady=(6, 10))

        nav = self.nav = tk.Frame(inner, bg=t.CARD)
        nav.pack(fill="x")
        self.back_btn = t.PillButton(nav, "←  Back", self.back, kind="ghost")
        self.next_btn = t.PillButton(nav, "Next  →", self.next, kind="primary")
        self.answer_btn = t.PillButton(nav, "Show answer", self.jump_answer, kind="secondary")
        self.back_btn.pack(side="left")
        self.next_btn.pack(side="left", padx=6)
        self.answer_btn.pack(side="right")

        ask = self.ask_row = tk.Frame(inner, bg=t.CARD)
        ask.pack(fill="x", pady=(12, 0))
        self.field = t.Field(ask, placeholder="Ask a follow-up…", width=30)
        self.field.pack(side="left", fill="x", expand=True)
        self.entry = self.field.entry
        self.entry.bind("<Return>", lambda _e: self._submit())
        self.entry.bind("<Escape>", lambda _e: self.close())
        self.ask_btn = t.PillButton(ask, "Ask", self._submit, kind="primary", height=34)
        self.ask_btn.pack(side="left", padx=(8, 0))

        self.footer = tk.Label(inner, text="", bg=t.CARD, fg=t.SUBTLE, font=f.tiny, anchor="w")
        self.footer.pack(fill="x", pady=(10, 0))
        self.win.bind("<Left>", lambda _e: self.back())
        self.win.bind("<Right>", lambda _e: self.next())
        self.win.withdraw()
        t.round_corners(self.win)

    # ---- states --------------------------------------------------------
    def prompt(self, near: tuple[int, int]) -> None:
        """Hotkey pressed: ask what they're stuck on (Enter with nothing = 'just look')."""
        self.state = "prompt"
        self.pages = []
        self.set_type_text("")
        self.title.config(text="What are you stuck on?")
        self.heading.config(text="")
        self._draw_progress()
        self._set_body("Type a question - or just press **Enter** and I'll look at what's under your cursor.")
        self.nav.pack_forget()
        self.entry.delete(0, "end")
        self.field.set_placeholder("e.g. why is this O(n²)?")
        self.ask_btn.config(text="Look")
        self.footer.config(text="Enter  ask   ·   Esc  close")
        self._refresh_modes()
        self._place(near)
        self._show(focus=True)

    def set_type_text(self, text: str) -> None:
        self.type_text = text or ""
        if not self.type_text:
            self.type_box.pack_forget()
            return
        lines = self.type_text.splitlines() or [""]
        preview = "\n".join(lines[:6]) + ("\n…" if len(lines) > 6 else "")
        self.type_preview.config(text=preview)
        if not self.type_box.winfo_ismapped():
            self.type_box.pack(fill="x", pady=(0, 10), before=self.hrow)

    def show_partial(self, fields: dict) -> None:
        """Streaming: show the title/summary/typing suggestion as soon as each one is finished."""
        if self.state != "thinking":
            return
        if fields.get("title"):
            self.title.config(text=fields["title"])
        if fields.get("summary"):
            self._set_body(fields["summary"] + "\n\nWorking out the steps…")
        if fields.get("type_text"):
            self.set_type_text(fields["type_text"])
        if self._anchor:
            self._place(*self._anchor)

    def thinking(self, near: tuple[int, int] | None = None) -> None:
        self.state = "thinking"
        self.set_type_text("")
        self.title.config(text="Looking at your screen…")
        self.heading.config(text="")
        self._draw_progress()
        self._set_body("Hang on - working it out.")
        self.nav.pack_forget()
        if near:
            self._place(near)
        self._show()

    def show_explanation(self, exp: Explanation, near: tuple[int, int], open_on_answer: bool, footer: str) -> None:
        self.state = "showing"
        self.pages = build_pages(exp)
        self.title.config(text=exp.title)
        self.set_type_text(exp.type_text)
        self.footer.config(text=footer)
        self.entry.delete(0, "end")
        self.field.set_placeholder("Ask a follow-up…")
        self.ask_btn.config(text="Ask")
        has_answer = any(p.kind == "answer" for p in self.pages)
        if not self.nav.winfo_ismapped():
            self.nav.pack(fill="x", before=self.ask_row)
        if has_answer:
            self.answer_btn.pack(side="right")
        else:
            self.answer_btn.pack_forget()
        self.idx = next((i for i, p in enumerate(self.pages) if p.kind == "answer"), 0) if open_on_answer else 0
        self._render(near)
        self._show()

    def close(self) -> None:
        self.state = "hidden"
        self.win.withdraw()
        self.on_close()

    # ---- navigation ----------------------------------------------------
    def next(self) -> None:
        if self.pages and self.idx < len(self.pages) - 1:
            self.idx += 1
            self._render()

    def back(self) -> None:
        if self.pages and self.idx > 0:
            self.idx -= 1
            self._render()

    def jump_answer(self) -> None:
        for i, p in enumerate(self.pages):
            if p.kind == "answer":
                self.idx = i
                self._render()
                return

    def current(self) -> Page | None:
        return self.pages[self.idx] if self.pages else None

    # ---- internals -----------------------------------------------------
    def _render(self, near: tuple[int, int] | None = None) -> None:
        page = self.pages[self.idx]
        self.heading.config(text=page.heading.upper(),
                            fg=t.SUCCESS if page.kind == "answer" else (t.VIOLET if page.kind in ("why", "check")
                                                                       else t.ACCENT_HI))
        self._set_body(page.text)
        self._draw_progress()
        self.back_btn.config(state="normal" if self.idx > 0 else "disabled")
        last = self.idx >= len(self.pages) - 1
        self.next_btn.config(state="disabled" if last else "normal")
        on_answer = page.kind == "answer"
        self.answer_btn.config(state="disabled" if on_answer else "normal")
        self.on_page(page)
        if page.point:
            self._place(page.point, beside=True)
        elif near:
            self._place(near)
        elif self._anchor:
            self._place(*self._anchor)  # re-clamp: the page may have grown

    def _draw_progress(self) -> None:
        c = self.progress
        c.delete("all")
        n = len(self.pages)
        if n < 2:
            return
        gap, dot, wide = 5, 6, 16
        x = 120 - (n - 1) * (dot + gap) - wide
        for i in range(n):
            if i == self.idx:
                t.round_rect(c, x, 1, x + wide, 1 + dot, 3, fill=t.ACCENT, outline="")
                x += wide + gap
            else:
                c.create_oval(x, 1, x + dot, 1 + dot, fill=t.SURFACE_HI if i > self.idx else t.ACCENT_LO,
                              outline="")
                x += dot + gap

    def _set_body(self, text: str) -> None:
        b = self.body
        b.config(state="normal")
        b.delete("1.0", "end")
        for chunk, code in split_code(text):
            if code:
                b.insert("end", "\n", ("codepad",))
                b.insert("end", chunk + "\n", ("code",))
                b.insert("end", "\n", ("codepad",))
            else:
                self._inline(chunk + "\n")
        b.delete("end-1c", "end")
        b.config(state="disabled")
        # Size the box to the wrapped text (pixel height / line height), capped so it never fills the screen.
        b.update_idletasks()
        line = t.measure_line(b)
        if b.winfo_width() <= 1:  # never shown yet: Tk would wrap at 1px, so estimate from characters
            px = (sum(max(1, -(-len(ln) // 44)) for ln in text.splitlines()) or 1) * (line + 5)
        else:
            try:
                px = b.count("1.0", "end", "update", "ypixels")  # "update" = lay out every line first
                px = px[0] if isinstance(px, tuple) else px
            except tk.TclError:
                px = 3 * line
        self.body_box.config(height=int(min(18 * line, max(2 * line, (px or line) + 4))))

    def _inline(self, text: str) -> None:
        """`code` and **bold** inside normal text."""
        for i, part in enumerate(re.split(r"(`[^`\n]+`|\*\*[^*\n]+\*\*)", text)):
            if i % 2 and part.startswith("`"):
                self.body.insert("end", part[1:-1], ("icode",))
            elif i % 2:
                self.body.insert("end", part[2:-2], ("b",))
            else:
                self.body.insert("end", part)

    def _submit(self) -> None:
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        if self.state == "prompt":
            self.on_ask(text)
        elif text:
            self.on_follow_up(text)

    def _pick_mode(self, mode: str) -> None:
        self.set_mode(mode)

    def _refresh_modes(self) -> None:
        cur = self.get_mode()
        if self.mode_var.get() != cur:
            self.mode_var.set(cur)

    def _show(self, focus: bool = False) -> None:
        self._refresh_modes()
        self.win.deiconify()
        self.win.attributes("-topmost", True)
        self.win.lift()
        if focus:
            self.win.focus_force()
            self.entry.focus_set()

    def _place(self, xy: tuple[int, int], beside: bool = False) -> None:
        self._anchor = (xy, beside)
        self.win.update_idletasks()
        w = max(self.win.winfo_reqwidth(), WIDTH)
        h = self.win.winfo_reqheight()
        left, top, right, bottom = monitor_bounds(*xy)
        if beside:
            # Sit under the thing being pointed at so the buddy and its label stay visible.
            x = xy[0] - 40
            y = xy[1] + 64
            if y + h > bottom - 8:
                y = xy[1] - h - 24
        else:
            x = xy[0] + 36
            if x + w > right - 8:
                x = xy[0] - 36 - w
            y = xy[1] + 12
        x = max(left + 8, min(x, right - w - 8))
        y = max(top + 8, min(y, bottom - h - 8))
        self.win.geometry(f"+{int(x)}+{int(y)}")

    def _drag_start(self, e) -> None:
        self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _drag_move(self, e) -> None:
        self.win.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")
