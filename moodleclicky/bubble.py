"""The Clippy-style pop-up: one idea per page, Back/Next, show-answer, follow-up questions."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass

from moodleclicky.brain import Explanation
from moodleclicky.capture import monitor_bounds
from moodleclicky.config import MODES

BG = "#fffbe0"
EDGE = "#3a3a3a"
INK = "#1d1d1d"
MUTED = "#6b6b6b"
FONT = ("Segoe UI", 11)
BOLD = ("Segoe UI", 12, "bold")
MONO = ("Consolas", 10)
WIDTH = 400


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
    ):
        self.root = root
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
        w.config(bg=EDGE)
        inner = self.inner = tk.Frame(w, bg=BG, padx=12, pady=10)
        inner.pack(padx=2, pady=2, fill="both", expand=True)

        head = tk.Frame(inner, bg=BG)
        head.pack(fill="x")
        self.title = tk.Label(head, text="MoodleClicky", bg=BG, fg=INK, font=BOLD, anchor="w",
                              wraplength=WIDTH - 80, justify="left")
        self.title.pack(side="left", fill="x", expand=True)
        for txt, cmd in (("✕", self.close), ("⚙", self.on_settings)):
            b = tk.Label(head, text=txt, bg=BG, fg=MUTED, font=("Segoe UI", 12), cursor="hand2", padx=4)
            b.pack(side="right")
            b.bind("<Button-1>", lambda _e, c=cmd: c())
        for wdg in (head, self.title):
            wdg.bind("<ButtonPress-1>", self._drag_start)
            wdg.bind("<B1-Motion>", self._drag_move)

        modes = tk.Frame(inner, bg=BG)
        modes.pack(fill="x", pady=(6, 4))
        self.mode_btns = {}
        for m in MODES:
            b = tk.Label(modes, text=m.capitalize(), font=("Segoe UI", 9), padx=8, pady=2, cursor="hand2")
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda _e, mm=m: self._pick_mode(mm))
            self.mode_btns[m] = b

        self.heading = tk.Label(inner, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold"), anchor="w")
        self.heading.pack(fill="x", pady=(4, 0))
        self.body = tk.Text(inner, width=46, height=4, wrap="word", bg=BG, fg=INK, font=FONT,
                            relief="flat", borderwidth=0, highlightthickness=0, cursor="arrow")
        self.body.tag_configure("code", font=MONO, background="#f1ecc8", lmargin1=6, lmargin2=6, rmargin=6)
        self.body.pack(fill="both", expand=True, pady=(2, 6))

        nav = self.nav = tk.Frame(inner, bg=BG)
        nav.pack(fill="x")
        self.back_btn = tk.Button(nav, text="◀ Back", command=self.back, relief="groove", bg=BG)
        self.next_btn = tk.Button(nav, text="Next ▶", command=self.next, relief="groove", bg=BG)
        self.answer_btn = tk.Button(nav, text="Show answer", command=self.jump_answer, relief="groove", bg=BG)
        self.back_btn.pack(side="left")
        self.next_btn.pack(side="left", padx=4)
        self.answer_btn.pack(side="right")

        ask = tk.Frame(inner, bg=BG)
        ask.pack(fill="x", pady=(8, 0))
        self.entry = tk.Entry(ask, font=FONT, relief="solid", borderwidth=1)
        self.entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.entry.bind("<Return>", lambda _e: self._submit())
        self.entry.bind("<Escape>", lambda _e: self.close())
        self.ask_btn = tk.Button(ask, text="Ask", command=self._submit, relief="groove", bg=BG)
        self.ask_btn.pack(side="left", padx=(4, 0))

        self.footer = tk.Label(inner, text="", bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.footer.pack(fill="x", pady=(6, 0))
        self.win.bind("<Left>", lambda _e: self.back())
        self.win.bind("<Right>", lambda _e: self.next())
        self.win.withdraw()

    # ---- states --------------------------------------------------------
    def prompt(self, near: tuple[int, int]) -> None:
        """Hotkey pressed: ask what they're stuck on (Enter with nothing = 'just look')."""
        self.state = "prompt"
        self.pages = []
        self.title.config(text="What are you stuck on?")
        self.heading.config(text="")
        self._set_body("Type a question, or just press Enter and I'll look at what's under your cursor.")
        self.nav.pack_forget()
        self.entry.delete(0, "end")
        self.footer.config(text="Esc to close  ·  Enter to ask")
        self._refresh_modes()
        self._place(near)
        self._show(focus=True)

    def thinking(self, near: tuple[int, int] | None = None) -> None:
        self.state = "thinking"
        self.title.config(text="Looking at your screen…")
        self.heading.config(text="")
        self._set_body("Hang on, working it out.")
        self.nav.pack_forget()
        if near:
            self._place(near)
        self._show()

    def show_explanation(self, exp: Explanation, near: tuple[int, int], open_on_answer: bool, footer: str) -> None:
        self.state = "showing"
        self.pages = build_pages(exp)
        self.title.config(text=exp.title)
        self.footer.config(text=footer)
        self.entry.delete(0, "end")
        has_answer = any(p.kind == "answer" for p in self.pages)
        if not self.nav.winfo_ismapped():
            self.nav.pack(fill="x", before=self.entry.master)
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
        self.heading.config(text=page.heading.upper())
        self._set_body(page.text)
        self.back_btn.config(state="normal" if self.idx > 0 else "disabled")
        self.next_btn.config(state="normal" if self.idx < len(self.pages) - 1 else "disabled")
        self.on_page(page)
        if page.point:
            self._place(page.point, beside=True)
        elif near:
            self._place(near)
        elif self._anchor:
            self._place(*self._anchor)  # re-clamp: the page may have grown

    def _set_body(self, text: str) -> None:
        b = self.body
        b.config(state="normal")
        b.delete("1.0", "end")
        for chunk, code in split_code(text):
            b.insert("end", chunk + "\n", ("code",) if code else ())
        b.config(state="disabled")
        lines = sum(max(1, len(line) // 44 + 1) for line in text.splitlines()) or 1
        b.config(height=min(18, max(3, lines)))

    def _submit(self) -> None:
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        if self.state == "prompt":
            self.on_ask(text)
        elif text:
            self.on_follow_up(text)

    def _pick_mode(self, mode: str) -> None:
        self.set_mode(mode)
        self._refresh_modes()

    def _refresh_modes(self) -> None:
        cur = self.get_mode()
        for m, b in self.mode_btns.items():
            on = m == cur
            b.config(bg="#2f80ed" if on else "#ece6c0", fg="white" if on else INK)

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
