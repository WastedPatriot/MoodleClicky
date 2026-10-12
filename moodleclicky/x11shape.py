"""Linux (X11): see-through, click-through overlay windows via the XShape extension.

Windows does this with a transparent colour key; Tk on X11 has no such thing, so instead we cut the window
to the outline of what's drawn on its canvas (bounding shape) and give it an empty input shape, so every
click goes straight through to the window underneath. Works without a compositor. On Wayland or without
libXext it quietly does nothing (the buddy is then a small box).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
import tkinter as tk

SHAPE_BOUNDING, SHAPE_INPUT = 0, 2
SHAPE_SET = 0


class XRectangle(ctypes.Structure):
    _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short),
                ("width", ctypes.c_ushort), ("height", ctypes.c_ushort)]


_x = None  # (libX11, libXext, Display*) once loaded, False if unavailable


def _libs():
    global _x
    if _x is None:
        _x = False
        if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
            try:
                x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
                xext = ctypes.CDLL(ctypes.util.find_library("Xext") or "libXext.so.6")
                x11.XOpenDisplay.restype = ctypes.c_void_p
                x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
                x11.XFlush.argtypes = [ctypes.c_void_p]
                x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
                x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                           ctypes.POINTER(ctypes.c_ulong),
                                           ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                                           ctypes.POINTER(ctypes.c_uint)]
                x11.XFree.argtypes = [ctypes.c_void_p]
                xext.XShapeCombineRectangles.argtypes = [
                    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    ctypes.POINTER(XRectangle), ctypes.c_int, ctypes.c_int, ctypes.c_int]
                dpy = x11.XOpenDisplay(None)
                if dpy:
                    _x = (x11, xext, dpy)
            except OSError:
                _x = False
    return _x or None


def available() -> bool:
    return _libs() is not None


def _xids(win: tk.Misc) -> list[int]:
    """The toplevel's own X window plus Tk's invisible wrapper around it. Both must be cut: the wrapper
    has no background, so any part of it left uncut shows stale pixels."""
    win.update_idletasks()
    inner = win.winfo_id()
    ids = [inner]
    x11, _xext, dpy = _libs()
    root, parent = ctypes.c_ulong(), ctypes.c_ulong()
    kids, n = ctypes.POINTER(ctypes.c_ulong)(), ctypes.c_uint()
    if x11.XQueryTree(dpy, inner, ctypes.byref(root), ctypes.byref(parent), ctypes.byref(kids), ctypes.byref(n)):
        if kids:
            x11.XFree(kids)
        if parent.value and parent.value != root.value:
            ids.append(parent.value)
    return ids


def _set(win: tk.Misc, kind: int, rects: list[tuple[int, int, int, int]]) -> bool:
    libs = _libs()
    if not libs:
        return False
    x11, xext, dpy = libs
    arr = (XRectangle * max(1, len(rects)))(*[XRectangle(x, y, w, h) for x, y, w, h in rects])
    for xid in _xids(win):
        xext.XShapeCombineRectangles(dpy, xid, kind, 0, 0, arr, len(rects), SHAPE_SET, 0)
    x11.XSync(dpy, 0)
    return True


def click_through(win: tk.Misc) -> bool:
    """Empty input shape: the pointer never 'hits' this window."""
    return _set(win, SHAPE_INPUT, [])


def mask_rects(mask) -> list[tuple[int, int, int, int]]:
    """A 1-bit PIL image -> as few (x, y, w, h) rectangles as is easy: horizontal runs, merged downwards."""
    w, h = mask.size
    px = mask.load()
    out, open_runs = [], {}  # (x0, x1) -> y where that run started
    for y in range(h + 1):
        runs = set()
        if y < h:
            x = 0
            while x < w:
                if px[x, y]:
                    x0 = x
                    while x < w and px[x, y]:
                        x += 1
                    runs.add((x0, x))
                else:
                    x += 1
        for run, y0 in list(open_runs.items()):
            if run not in runs:
                out.append((run[0], y0, run[1] - run[0], y - y0))
                del open_runs[run]
        for run in runs:
            open_runs.setdefault(run, y)
    return out


def canvas_mask(canvas: tk.Canvas, w: int, h: int):
    """Rasterise what's drawn on a canvas (polygons, ovals, rectangles, lines, text boxes) into a mask."""
    from PIL import Image, ImageDraw

    img = Image.new("1", (max(1, w), max(1, h)), 0)
    d = ImageDraw.Draw(img)
    for item in canvas.find_all():
        kind = canvas.type(item)
        xy = canvas.coords(item)
        try:
            fill = canvas.itemcget(item, "fill")
        except tk.TclError:
            fill = ""
        try:
            outline = canvas.itemcget(item, "outline")
            width = max(1, round(float(canvas.itemcget(item, "width") or 1)))
        except tk.TclError:
            outline, width = "", 1
        if kind == "polygon" and len(xy) >= 6:
            pts = list(zip(xy[0::2], xy[1::2], strict=False))
            if fill:
                d.polygon(pts, fill=1)
            if outline:
                d.line(pts + pts[:1], fill=1, width=width + 1)
        elif kind in ("oval", "rectangle") and len(xy) == 4:
            box = [min(xy[0], xy[2]), min(xy[1], xy[3]), max(xy[0], xy[2]), max(xy[1], xy[3])]
            draw = d.ellipse if kind == "oval" else d.rectangle
            if fill:
                draw(box, fill=1)
            elif outline:
                draw(box, outline=1, width=width + 1)
        elif kind == "line" and len(xy) >= 4:
            d.line(list(zip(xy[0::2], xy[1::2], strict=False)), fill=1, width=width + 1)
        elif kind == "text":
            bb = canvas.bbox(item)
            if bb:
                d.rectangle(bb, fill=1)
    return img


class Shaper:
    """Keeps one overlay window cut to its canvas drawing; only talks to X when the outline changes."""

    def __init__(self, win: tk.Misc, canvas: tk.Canvas):
        self.win, self.canvas = win, canvas
        self._last = None
        self.enabled = available()

    def update(self, w: int, h: int) -> None:
        if not self.enabled:
            return
        try:
            mask = canvas_mask(self.canvas, w, h)
            sig = (mask.size, mask.tobytes())
            if sig == self._last:
                return
            self._last = sig
            _set(self.win, SHAPE_BOUNDING, mask_rects(mask))
            click_through(self.win)
        except Exception:  # never let a cosmetic nicety take the app down
            self.enabled = False
