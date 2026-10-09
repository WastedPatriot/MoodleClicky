"""Windows-only niceties: crisp DPI and click-through overlay windows. No-ops elsewhere."""

from __future__ import annotations

import sys

IS_WIN = sys.platform == "win32"


def enable_dpi_awareness() -> None:
    """Make Tk, mss and the mouse all agree on real pixel coordinates."""
    if not IS_WIN:
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # nosec B110 - very old Windows, carry on blurry
            pass


def make_click_through(widget) -> None:
    """Let mouse clicks pass straight through a window (used for the buddy sprite)."""
    if not IS_WIN:
        return
    import ctypes

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    user32 = ctypes.windll.user32
    widget.update_idletasks()
    hwnd = user32.GetParent(widget.winfo_id()) or widget.winfo_id()
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(
        hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    )


def com_init() -> None:
    """Audio threads on Windows need COM initialised per thread (WASAPI via `soundcard`)."""
    if not IS_WIN:
        return
    import ctypes

    try:
        ctypes.windll.ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
    except Exception:  # nosec B110 - already initialised in this thread
        pass
