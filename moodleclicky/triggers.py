"""Wake-up triggers: double-tap either Ctrl (default), Right Ctrl only, triple tap, one tap - plus the
Copilot key (it sends F23) on laptops that have one instead of a Right Ctrl.

(If you use PowerToys "Find My Mouse", which also listens for Left Ctrl x2, pick "Right Ctrl x2".)

A Ctrl *tap* only counts when Ctrl is pressed and released on its own - so Ctrl+C, Ctrl+V, Ctrl+click etc.
never trigger it. Two taps within `window` seconds = trigger. Pure logic here (DoubleTap) so it's unit
tested; `KeyTrigger` wires it to a global pynput keyboard listener.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable

TRIGGERS = ("double_rctrl", "double_ctrl", "triple_ctrl", "right_ctrl", "hotkey")
TRIGGER_LABELS = {
    "double_rctrl": "Double-tap Right Ctrl",
    "double_ctrl": "Double-tap either Ctrl",
    "triple_ctrl": "Triple-tap either Ctrl",
    "right_ctrl": "Tap Right Ctrl on its own",
    "hotkey": "Ctrl + Alt + Q (classic hotkey)",
}


class DoubleTap:
    """Feed it key events; it calls `fire()` on a clean double tap of the watched key(s).

    Holding the key on its own for `hold_after` seconds is push-to-talk instead: `on_hold_start()` fires
    (call `check_hold()` from a timer), then `on_hold_end()` when it's released - or `on_hold_cancel()` if
    another key gets pressed meanwhile (e.g. Ctrl+C while holding).
    """

    def __init__(self, fire: Callable[[], None], taps: int = 2, window: float = 0.55, max_hold: float = 0.40,
                 clock: Callable[[], float] = time.monotonic, hold_after: float = 0.50,
                 on_tap: Callable[[int], None] | None = None,
                 on_hold_start: Callable[[], None] | None = None, on_hold_end: Callable[[], None] | None = None,
                 on_hold_cancel: Callable[[], None] | None = None,
                 on_extra: Callable[[], None] | None = None, extra_wait: float = 0.35):
        self.fire = fire
        # One more tap than needed (e.g. Ctrl x3 when Ctrl x2 wakes it) = on_extra() instead. To tell them apart
        # the normal trigger waits `extra_wait` after its last tap; call resolve() from a timer.
        self.on_extra = on_extra
        self.extra_wait = extra_wait
        self.pending_since: float | None = None
        self.on_tap = on_tap  # each clean tap that doesn't finish the sequence (for "I heard you" feedback)
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
        self.pending_since = None  # a hold after a double tap is push-to-talk, not both
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
            self.pending_since = None
            return
        if self.pending_since is not None:  # the extra tap: e.g. Ctrl x3 = ask a question
            self.pending_since = None
            self._taps.clear()
            self.on_extra()
            return
        span = self.window * max(1, self.taps_needed - 1)  # each gap may be up to `window`
        self._taps = [t for t in self._taps if now - t <= span] + [now]
        if len(self._taps) >= self.taps_needed:
            self._taps.clear()
            if self.on_extra:
                self.pending_since = now  # wait a moment: is another tap coming?
            else:
                self.fire()
        elif self.on_tap:
            self.on_tap(len(self._taps))

    def resolve(self) -> None:
        """Timer callback after a completed sequence: no extra tap came, so it's the normal trigger."""
        if (self.pending_since is None or self._down_at is not None
                or self.clock() - self.pending_since < self.extra_wait - 0.01):
            return  # still waiting, or a third press is in progress (its release decides)
        self.pending_since = None
        self.fire()

    def other_key(self) -> None:
        if self.pending_since is not None and self._down_at is None:  # a finished double tap, then typing
            self.pending_since = None
            self.fire()
        if self.holding:  # e.g. Ctrl+C while holding: that wasn't push-to-talk after all
            self.holding = False
            if self.on_hold_cancel:
                self.on_hold_cancel()
        if self._down_at is not None:
            self._dirty = True  # e.g. Ctrl+C
        self._taps.clear()  # typing between taps cancels


class KeyTrigger:
    """Global listener: 'double_ctrl' (either Ctrl twice), 'double_rctrl' (Right Ctrl twice), 'triple_ctrl',
    'right_ctrl' (Right Ctrl once). The Copilot key (F23) always works as a one-press trigger too."""

    COPILOT_VK = 0x86  # VK_F23 - what the Copilot key sends (with Win+Shift)

    def __init__(self, mode: str, fire: Callable[[], None], on_escape: Callable[[], None] | None = None,
                 on_hold_start=None, on_hold_end=None, on_hold_cancel=None, on_tap=None, on_extra=None):
        import threading

        self.mode = mode
        self.on_escape = on_escape
        self.tap = DoubleTap(fire, taps={"right_ctrl": 1, "triple_ctrl": 3}.get(mode, 2), on_tap=on_tap,
                             on_hold_start=on_hold_start, on_hold_end=on_hold_end, on_hold_cancel=on_hold_cancel,
                             on_extra=on_extra)
        self._lock = threading.RLock()  # key listener, mouse listener and timers all poke the same state
        self._listener = None
        self._mouse = None
        self._timer = None

    def _is_watched(self, key, keyboard) -> bool:
        if self.mode in ("right_ctrl", "double_rctrl"):
            return key == keyboard.Key.ctrl_r
        return key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r)

    def _later(self, secs: float, fn):
        import threading

        def run():
            with self._lock:
                fn()

        timer = threading.Timer(secs, run)
        timer.daemon = True
        timer.start()
        return timer

    def start(self) -> None:
        from pynput import keyboard

        def on_press(key):
            with self._lock:
                handle_press(key)

        def handle_press(key):
            if self._is_watched(key, keyboard):
                first = self.tap._down_at is None
                self.tap.watched_down()
                if first and self.tap.on_hold_start:  # push-to-talk if still held in a moment
                    self._timer = self._later(self.tap.hold_after + 0.02, self.tap.check_hold)
            else:
                self.tap.other_key()
                if key == keyboard.Key.esc and self.on_escape:
                    self.on_escape()
                elif self._vk(key) == self.COPILOT_VK and not self.tap.paused:
                    self.tap.fire()

        def on_release(key):
            if not self._is_watched(key, keyboard):
                return
            with self._lock:
                if self._timer:
                    self._timer.cancel()
                was_pending = self.tap.pending_since is not None
                self.tap.watched_up()
                if self.tap.pending_since is not None and not was_pending:  # Ctrl x2: wait for a 3rd tap
                    self._later(self.tap.extra_wait, self.tap.resolve)
                elif was_pending and self.tap.pending_since is not None:  # resolve ran early: try again
                    self._later(0.05, self.tap.resolve)

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()
        try:  # Ctrl+click (multi-select, open in new tab) is neither a tap nor push-to-talk
            from pynput import mouse

            def on_click(*_a):
                with self._lock:
                    self.tap.other_key()

            self._mouse = mouse.Listener(on_click=on_click)
            self._mouse.daemon = True
            self._mouse.start()
        except Exception:  # nosec B110 - keyboard trigger still works without it
            self._mouse = None

    @staticmethod
    def _vk(key) -> int | None:
        vk = getattr(key, "vk", None)
        if vk is None:
            vk = getattr(getattr(key, "value", None), "vk", None)
        return vk

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
        if self._mouse:
            self._mouse.stop()
            self._mouse = None


# ---- hotkeys (Ctrl+Alt+Q etc.) -------------------------------------------------
# pynput's GlobalHotKeys matches on the *character* a key makes. On UK and most European layouts Ctrl+Alt is
# AltGr, so Ctrl+Alt+Q arrives as a different character (or none) and never matches. We match on which
# physical key it is (virtual-key code) instead, and treat AltGr as Ctrl+Alt.

MODIFIERS = {"ctrl": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl", "alt": "alt", "alt_l": "alt", "alt_r": "alt",
             "alt_gr": "alt", "shift": "shift", "shift_l": "shift", "shift_r": "shift", "cmd": "cmd",
             "cmd_l": "cmd", "cmd_r": "cmd"}


def parse_combo(combo: str) -> tuple[frozenset, str]:
    """'<ctrl>+<alt>+q' -> ({'ctrl', 'alt'}, 'q'). Raises ValueError if it has no (or two) main keys."""
    mods, key = set(), None
    for part in combo.lower().replace(" ", "").split("+"):
        name = part.strip("<>")
        if not name:
            continue
        if name in MODIFIERS:
            mods.add(MODIFIERS[name])
        elif key is None:
            key = name
        else:
            raise ValueError(f"two main keys in {combo!r}")
    if not key:
        raise ValueError(f"no main key in {combo!r}")
    return frozenset(mods), key


def key_ident(key, platform: str = sys.platform) -> str:
    """A layout-independent name for a pynput key: 'ctrl', 'alt', 'q', '7', 'space', 'f5'…"""
    name = getattr(key, "name", None)
    if name:  # pynput.keyboard.Key member
        return MODIFIERS.get(name, name)
    vk = getattr(key, "vk", None)
    if isinstance(vk, int):
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        if 0x41 <= vk <= 0x5A:  # Windows VK_A..VK_Z / X11 uppercase keysyms
            return chr(vk).lower()
        if platform != "win32" and 0x61 <= vk <= 0x7A:  # X11 lowercase keysyms (on Windows these are numpad)
            return chr(vk)
    char = getattr(key, "char", None)
    if char and char.isprintable():
        return char.lower()
    return f"vk{vk}" if vk is not None else ""


class Hotkeys:
    """{'<ctrl>+<alt>+q': fn, ...} -> calls fn when exactly those modifiers + that key are pressed."""

    def __init__(self, combos: dict[str, Callable[[], None]]):
        self.combos = {}
        for combo, fn in combos.items():
            try:
                self.combos[parse_combo(combo)] = fn
            except ValueError:
                continue  # a typo in Settings shouldn't kill the other hotkeys
        self.held: set[str] = set()
        self._down: set[str] = set()
        self._listener = None

    def press(self, ident: str) -> None:
        if ident in ("ctrl", "alt", "shift", "cmd"):
            self.held.add(ident)
            return
        if ident in self._down:  # auto-repeat
            return
        self._down.add(ident)
        fn = self.combos.get((frozenset(self.held), ident))
        if fn:
            fn()

    def release(self, ident: str) -> None:
        self.held.discard(ident)
        self._down.discard(ident)

    def start(self) -> None:
        from pynput import keyboard

        self._listener = keyboard.Listener(on_press=lambda k: self.press(key_ident(k)),
                                           on_release=lambda k: self.release(key_ident(k)))
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
