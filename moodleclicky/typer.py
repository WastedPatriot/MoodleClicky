"""Put text into the box you were typing in: refocus that window, paste, restore your clipboard.

Pasting (Ctrl+V) rather than simulating each key keeps code indentation intact and works in browsers,
Word and IDEs alike. Our own Ctrl presses are hidden from the double-tap trigger via `pause`.
"""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable

from moodleclicky.winutil import focus_window


def type_into(root: tk.Misc, hwnd: int | None, text: str, pause: Callable[[bool], None] = lambda on: None,
              keyboard=None) -> None:
    if not text:
        return
    try:
        old = root.clipboard_get()
    except tk.TclError:
        old = None
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()  # make sure the clipboard is published before the paste
    if keyboard is None:
        from pynput.keyboard import Controller

        keyboard = Controller()
    from pynput.keyboard import Key

    pause(True)
    try:
        focus_window(hwnd)
        time.sleep(0.15)
        with keyboard.pressed(Key.ctrl):
            keyboard.press("v")
            keyboard.release("v")
        time.sleep(0.25)
    finally:
        pause(False)

    def restore():
        try:
            root.clipboard_clear()
            if old is not None:
                root.clipboard_append(old)
        except tk.TclError:
            pass

    root.after(600, restore)
