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
    """Feed it key events; it calls `fire()` on a clean double tap of the watched key(s).

    Holding the key on its own for `hold_after` seconds is push-to-talk instead: `on_hold_start()` fires
    (call `check_hold()` from a timer), then `on_hold_end()` when it's released - or `on_hold_cancel()` if
    another key gets pressed meanwhile (e.g. Ctrl+C while holding).
    """

    def __init__(self, fire: Callable[[], None], taps: int = 2, window: float = 0.40, max_hold: float = 0.35,
                 clock: Callable[[], float] = time.monotonic, hold_after: float = 0.45,
                 on_hold_start: Callable[[], None] | None = None, on_hold_end: Callable[[], None] | None = None,
                 on_hold_cancel: Callable[[], None] | None = None):
        self.fire = fire
        self.hold_after = hold_after
        self.on_hold_start = on_hold_start
        self.on_hold_end = on_hold_end
        self.on_hold_cancel = on_hold_cancel
        self.holding = False
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

    def check_hold(self) -> None:
        """Call ~hold_after after a key-down: starts push-to-talk if the key is still held on its own."""
        if (self._down_at is None or self._dirty or self.holding or self.paused or not self.on_hold_start
                or self.clock() - self._down_at < self.hold_after):
            return
        self.holding = True
        self._taps.clear()
        self.on_hold_start()

    def watched_up(self) -> None:
        if self._down_at is None:
            return
        if self.holding:
            self.holding = False
            self._down_at = None
            if self.on_hold_end:
                self.on_hold_end()
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
        if self.holding:  # e.g. Ctrl+C while holding: that wasn't push-to-talk after all
            self.holding = False
            if self.on_hold_cancel:
                self.on_hold_cancel()
        if self._down_at is not None:
            self._dirty = True  # e.g. Ctrl+C
        self._taps.clear()  # typing between taps cancels


class KeyTrigger:
    """Global listener: 'double_rctrl' (Right Ctrl twice), 'double_ctrl' (either Ctrl twice) or
    'right_ctrl' (Right Ctrl once)."""

    def __init__(self, mode: str, fire: Callable[[], None], on_escape: Callable[[], None] | None = None,
                 on_hold_start=None, on_hold_end=None, on_hold_cancel=None):
        self.mode = mode
        self.on_escape = on_escape
        self.tap = DoubleTap(fire, taps={"right_ctrl": 1, "triple_ctrl": 3}.get(mode, 2),
                             on_hold_start=on_hold_start, on_hold_end=on_hold_end, on_hold_cancel=on_hold_cancel)
        self._listener = None
        self._timer = None

    def _is_watched(self, key, keyboard) -> bool:
        if self.mode in ("right_ctrl", "double_rctrl"):
            return key == keyboard.Key.ctrl_r
        return key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r)

    def start(self) -> None:
        from pynput import keyboard

        def on_press(key):
            if self._is_watched(key, keyboard):
                first = self.tap._down_at is None
                self.tap.watched_down()
                if first and self.tap.on_hold_start:  # push-to-talk if still held in a moment
                    import threading

                    self._timer = threading.Timer(self.tap.hold_after + 0.02, self.tap.check_hold)
                    self._timer.daemon = True
                    self._timer.start()
            else:
                self.tap.other_key()
                if key == keyboard.Key.esc and self.on_escape:
                    self.on_escape()

        def on_release(key):
            if self._is_watched(key, keyboard):
                if self._timer:
                    self._timer.cancel()
                self.tap.watched_up()

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
