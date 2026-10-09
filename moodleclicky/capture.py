"""Grab the monitor the cursor is on, mark where the cursor is, shrink it for Claude."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw


@dataclass
class Shot:
    image: bytes  # JPEG (fast to encode, small to upload)
    width: int  # image size sent to Claude
    height: int
    left: int  # monitor origin on the virtual desktop
    top: int
    scale: float  # image px per screen px
    cursor: tuple[int, int]  # cursor position in image px

    media_type: str = "image/jpeg"

    def to_screen(self, x: float, y: float) -> tuple[int, int] | None:
        """Image coordinates from Claude -> real screen coordinates. None if off-image."""
        if x < 0 or y < 0 or x > self.width or y > self.height:
            return None
        return int(self.left + x / self.scale), int(self.top + y / self.scale)


def monitor_for(monitors: list[dict], x: int, y: int) -> dict:
    """Pick the mss monitor containing (x, y). monitors[0] is the whole virtual desktop."""
    for m in monitors[1:]:
        if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]:
            return m
    return monitors[1] if len(monitors) > 1 else monitors[0]


def build_shot(img: Image.Image, left: int, top: int, cursor_xy: tuple[int, int], max_edge: int) -> Shot:
    """Scale an RGB screenshot and draw a ring where the cursor is."""
    scale = min(1.0, max_edge / max(img.width, img.height))
    if scale < 1.0:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    cx = round((cursor_xy[0] - left) * scale)
    cy = round((cursor_xy[1] - top) * scale)
    draw = ImageDraw.Draw(img)
    r = max(10, round(18 * scale))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 0, 90), width=3)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)  # ~10x faster than optimised PNG and a fraction of the size
    return Shot(buf.getvalue(), img.width, img.height, left, top, scale, (cx, cy))


def _mss():
    import mss

    return getattr(mss, "MSS", None) or mss.mss  # mss >= 10 renamed the class


def grab(cursor_xy: tuple[int, int], max_edge: int = 1568) -> Shot:
    with _mss()() as sct:
        mon = monitor_for(sct.monitors, *cursor_xy)
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    return build_shot(img, mon["left"], mon["top"], cursor_xy, max_edge)


def monitor_bounds(x: int, y: int) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the monitor containing (x, y)."""
    try:
        with _mss()() as sct:
            m = monitor_for(sct.monitors, x, y)
    except Exception:
        return 0, 0, 1920, 1080
    return m["left"], m["top"], m["left"] + m["width"], m["top"] + m["height"]
