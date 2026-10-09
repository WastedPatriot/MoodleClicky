"""Wake-up triggers that don't clash with anything: double-tap Right Ctrl (default), either Ctrl, or one tap.

Right Ctrl is the default because double-tapping *Left* Ctrl is PowerToys "Find My Mouse"'s shortcut.

A Ctrl *tap* only counts when Ctrl is pressed and released on its own - so Ctrl+C, Ctrl+V, Ctrl+click etc.
never trigger it. Two taps within `window` seconds = trigger. Pure logic here (DoubleTap) so it's unit
tested; `KeyTrigger` wires it to a global pynput keyboard listener.
"""

from __future__ import annotations

import time
from collections.abc import Callable

TRIGGERS = ("double_rctrl", "double_ctrl", "triple_ctrl", "right_ctrl", "hotkey")
TRIGGER_LABELS = {
    "double_rctrl": "Double-tap Right Ctrl",
    "double_ctrl": "Double-tap either Ctrl",
    "triple_ctrl": "Triple-tap either Ctrl",
    "right_ctrl": "Tap Right Ctrl on its own",
    "hotkey": "Ctrl + Alt + Space (classic hotkey)",
}


class DoubleTap:
    """Feed it key events; it calls `fire()` on a clean double tap of the watched key(s)."""

    def __init__(self, fire: Callable[[], None], taps: int = 2, window: float = 0.40, max_hold: float = 0.35,
                 clock: Callable[[], float] = time.monotonic):
        self.fire = fire
        self.taps_needed = taps
        self.window = window
        self.max_hold = max_hold
        self.clock = clock
        self.paused = False  # set while we type into another app ourselves
        self._down_at: float | None = None
        self._dirty = False  # another key was used while the watched key was down
        self._taps: list[float] = []

    def watched_down(self) -> None:
        if self._down_at is None:  # ignore auto-repeat
            self._down_at = self.clock()
            self._dirty = False

    def watched_up(self) -> None:
        if self._down_at is None:
            return
        now = self.clock()
        clean = not self._dirty and (now - self._down_at) <= self.max_hold
        self._down_at = None
        if not clean or self.paused:
            self._taps.clear()
            return
        span = self.window * max(1, self.taps_needed - 1)  # each gap may be up to `window`
        self._taps = [t for t in self._taps if now - t <= span] + [now]
        if len(self._taps) >= self.taps_needed:
            self._taps.clear()
            self.fire()

    def other_key(self) -> None:
        if self._down_at is not None:
            self._dirty = True  # e.g. Ctrl+C
        self._taps.clear()  # typing between taps cancels


class KeyTrigger:
    """Global listener: 'double_rctrl' (Right Ctrl twice), 'double_ctrl' (either Ctrl twice) or
    'right_ctrl' (Right Ctrl once)."""

    def __init__(self, mode: str, fire: Callable[[], None], on_escape: Callable[[], None] | None = None):
        self.mode = mode
        self.on_escape = on_escape
        self.tap = DoubleTap(fire, taps={"right_ctrl": 1, "triple_ctrl": 3}.get(mode, 2))
        self._listener = None

    def _is_watched(self, key, keyboard) -> bool:
        if self.mode in ("right_ctrl", "double_rctrl"):
            return key == keyboard.Key.ctrl_r
        return key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r)

    def start(self) -> None:
        from pynput import keyboard

        def on_press(key):
            if self._is_watched(key, keyboard):
                self.tap.watched_down()
            else:
                self.tap.other_key()
                if key == keyboard.Key.esc and self.on_escape:
                    self.on_escape()

        def on_release(key):
            if self._is_watched(key, keyboard):
                self.tap.watched_up()

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
