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


# ---- start with Windows ------------------------------------------------------
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> str:
    """How to start this app: the .exe when frozen, otherwise pythonw -m moodleclicky."""
    import os

    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return f'"{pyw if os.path.exists(pyw) else exe}" -m moodleclicky'


def set_autostart(enabled: bool, name: str = "MoodleClicky") -> bool:
    if not IS_WIN:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


# ---- single instance ---------------------------------------------------------
_PORT = 48713  # localhost only


class SingleInstance:
    """Only one MoodleClicky at a time. A second launch pokes the first one (which shows itself) and exits."""

    def __init__(self, on_poke=None):
        import socket
        import threading

        self.primary = False
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if not IS_WIN:
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("127.0.0.1", _PORT))
            self._sock.listen(1)
            self.primary = True
        except OSError:
            self._sock.close()
            try:
                with socket.create_connection(("127.0.0.1", _PORT), timeout=1) as c:
                    c.sendall(b"show")
            except OSError:
                self.primary = True  # port taken by something else: just run
            return

        def serve():
            while True:
                try:
                    conn, _ = self._sock.accept()
                    with conn:
                        if conn.recv(16) == b"show" and on_poke:
                            on_poke()
                except OSError:
                    return

        threading.Thread(target=serve, name="single-instance", daemon=True).start()


# ---- whose window has the keyboard ---------------------------------------------
def foreground_window() -> int | None:
    """Handle of the window you were typing in (so we can give focus back / type into it)."""
    if not IS_WIN:
        return None
    import ctypes

    try:
        return int(ctypes.windll.user32.GetForegroundWindow()) or None
    except Exception:
        return None


def focus_window(hwnd: int | None) -> bool:
    if not (IS_WIN and hwnd):
        return False
    import ctypes

    try:
        return bool(ctypes.windll.user32.SetForegroundWindow(hwnd))
    except Exception:
        return False
