"""Move the real mouse pointer to the answer, smoothly, so it's ready to click (Ctrl+Alt+A / "Show me")."""

from __future__ import annotations

import math
import tkinter as tk


def glide_path(start: tuple[int, int], end: tuple[int, int], steps: int = 18) -> list[tuple[int, int]]:
    """Points from start to end with ease-in-out, ending exactly on `end`."""
    (x0, y0), (x1, y1) = start, end
    out = []
    for i in range(1, steps + 1):
        k = (1 - math.cos(math.pi * i / steps)) / 2
        out.append((round(x0 + (x1 - x0) * k), round(y0 + (y1 - y0) * k)))
    return out


def glide(root: tk.Misc, to: tuple[int, int], mouse=None, ms: int = 320) -> None:
    """Glide the pointer to `to` (screen coordinates) over ~`ms` milliseconds. Never clicks."""
    if mouse is None:
        from pynput.mouse import Controller

        mouse = Controller()
    start = tuple(int(v) for v in mouse.position)
    path = glide_path(start, to)
    delay = max(1, ms // len(path))

    def step(i: int = 0) -> None:
        mouse.position = path[i]
        if i + 1 < len(path):
            root.after(delay, step, i + 1)

    step()
