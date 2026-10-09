"""The cursor buddy: a little arrow with eyes that trails your mouse and flies off to point at things."""

from __future__ import annotations

import math
import tkinter as tk

from moodleclicky.winutil import IS_WIN, make_click_through

KEY = "#010203"  # transparent colour key (Windows)
TIP = (18, 18)  # arrow tip inside the canvas (room around it for the pulse ring)
BASE_W, BASE_H = 52, 66
FOLLOW_OFFSET = (14, 18)  # tip sits just below-right of the real cursor


class Buddy:
    def __init__(self, root: tk.Tk, color: str = "#2f80ed", bg: str | None = None):
        self.root = root
        self.color = color
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        if IS_WIN:
            self.win.config(bg=KEY)
            self.win.attributes("-transparentcolor", KEY)
        # Without a transparent colour key (macOS/Linux) the window is a small box in `bg`.
        self.canvas = tk.Canvas(self.win, width=BASE_W, height=BASE_H, bg=KEY if IS_WIN else (bg or "#ffffff"),
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.size = (BASE_W, BASE_H)
        self.win.geometry(f"{BASE_W}x{BASE_H}+0+0")
        make_click_through(self.win)

        self.x, self.y = 0.0, 0.0
        self.target_point: tuple[int, int] | None = None
        self.label = ""
        self.thinking = False
        self.visible = True
        self._phase = 0.0
        self._last = (0.0, 0.0)
        self._draw()
        self._tick()

    # ---- public --------------------------------------------------------
    def set_color(self, color: str) -> None:
        self.color = color

    def show(self) -> None:
        self.visible = True
        self.win.deiconify()
        self.win.attributes("-topmost", True)

    def hide(self) -> None:
        self.visible = False
        self.win.withdraw()

    def point_at(self, xy: tuple[int, int] | None, label: str = "") -> None:
        self.target_point = xy
        self.label = label if xy else ""

    def follow(self) -> None:
        self.point_at(None)

    def set_thinking(self, on: bool) -> None:
        self.thinking = on

    def position(self) -> tuple[int, int]:
        """Where the arrow tip is on screen right now."""
        return int(self.x), int(self.y)

    # ---- animation -----------------------------------------------------
    # self.x / self.y are the arrow TIP on screen; the window is laid out around it.
    def _tick(self) -> None:
        try:
            if self.target_point:
                tx, ty = self.target_point
                ease = 0.12
            else:
                px, py = self.root.winfo_pointerxy()
                tx, ty = px + FOLLOW_OFFSET[0], py + FOLLOW_OFFSET[1]
                ease = 0.28
            self._last = (self.x, self.y)
            self.x += (tx - self.x) * ease
            self.y += (ty - self.y) * ease
            self._phase += 0.15
            if self.visible:
                ox, oy = self._draw()
                self.win.geometry(f"{self.size[0]}x{self.size[1]}+{int(self.x) - ox}+{int(self.y) - oy}")
        except tk.TclError:
            return  # window destroyed
        self.root.after(16, self._tick)

    def _draw(self) -> tuple[int, int]:
        """Redraw; returns where the tip sits inside the canvas."""
        c = self.canvas
        c.delete("all")
        font = ("Segoe UI", 10, "bold")
        label_w = self._font_width(font, self.label) + 12 if self.target_point and self.label else 0
        # Label goes to the LEFT of the tip (usually margin/indent there), unless we're at the screen edge.
        label_left = bool(label_w) and self.x - label_w - 30 > 0
        ox = TIP[0] + (label_w + 14 if label_left else 0)
        oy = TIP[1]
        w = ox + BASE_W - TIP[0] + (40 if self.thinking else 0) + (label_w + 30 if label_w and not label_left else 0)

        bob = math.sin(self._phase) * 1.5 if not self.target_point else 0
        pts = [(0, 0), (0, 34), (9, 26), (16, 42), (23, 39), (16, 24), (28, 24)]
        poly = [v for x, y in pts for v in (ox + x, oy + y + bob)]
        c.create_polygon(poly, fill=self.color, outline="white", width=2, joinstyle="round")

        # Eyes look the way we're moving.
        dx, dy = self.x - self._last[0], self.y - self._last[1]
        d = math.hypot(dx, dy) or 1.0
        lx, ly = (dx / d * 1.5, dy / d * 1.5) if d > 0.5 else (0.0, 0.0)
        for ex, ey in ((5, 15), (11, 18)):
            ex, ey = ox + ex, oy + ey + bob
            c.create_oval(ex - 3, ey - 3, ex + 3, ey + 3, fill="white", outline="")
            c.create_oval(ex - 1.3 + lx, ey - 1.3 + ly, ex + 1.3 + lx, ey + 1.3 + ly, fill="#111", outline="")

        if self.target_point:
            r = 9 + 4 * (1 + math.sin(self._phase * 2))
            c.create_oval(ox - r, oy - r, ox + r, oy + r, outline=self.color, width=2)
            if label_w:
                lx0 = ox - 14 - label_w if label_left else ox + 30
                c.create_rectangle(lx0, oy - 10, lx0 + label_w, oy + 10, fill=self.color, outline="")
                c.create_text(lx0 + label_w / 2, oy, text=self.label, fill="white", font=font)
        if self.thinking:
            for i in range(3):
                a = 0.5 + 0.5 * math.sin(self._phase * 2 - i)
                r = 2 + 1.5 * a
                cx, cy = ox + 36 + i * 10, oy + 30
                c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self.color, outline="")
        self.size = (int(w), BASE_H)
        return ox, oy

    def _font_width(self, font, text: str) -> int:
        if not text:
            return 0
        if getattr(self, "_font_cache", (None, None))[0] != font:
            import tkinter.font as tkfont

            self._font_cache = (font, tkfont.Font(root=self.root, font=font))
        return self._font_cache[1].measure(text)
