"""Push-to-talk: hold Right Ctrl, speak, let go. Records the mic while held and transcribes it on this PC."""

from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np

RATE = 16000
BLOCK = 1600  # 0.1 s
MAX_SECONDS = 60


def default_mic():
    import soundcard as sc

    return sc.default_microphone().recorder(samplerate=RATE, channels=1, blocksize=BLOCK)


class VoiceRecorder:
    """start() begins capturing in a thread; stop() returns 16 kHz mono float32 audio."""

    def __init__(self, open_recorder: Callable[[], object] = default_mic):
        self.open_recorder = open_recorder
        self.level = 0.0
        self.error = ""
        self._blocks: list[np.ndarray] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._blocks, self.error, self.level = [], "", 0.0
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="push-to-talk", daemon=True)
        self._thread.start()

    def stop(self) -> np.ndarray:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if not self._blocks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._blocks).astype(np.float32)

    def _run(self) -> None:
        from moodleclicky.winutil import com_init

        com_init()
        try:
            with self.open_recorder() as rec:
                while not self._stop.is_set() and len(self._blocks) * BLOCK < MAX_SECONDS * RATE:
                    data = np.asarray(rec.record(numframes=BLOCK), dtype=np.float32)
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    self._blocks.append(data)
                    self.level = float(min(1.0, np.sqrt(np.mean(data ** 2)) * 6))
        except Exception as e:  # no microphone, permission denied, device unplugged
            self.error = str(e) or type(e).__name__


def transcribe_question(transcriber, audio: np.ndarray, course: str = "") -> str:
    """Speech -> one clean line of text ('' if nothing was said)."""
    if len(audio) < RATE // 3:  # under ~0.3 s: a stray press
        return ""
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 0:
        audio = audio / max(peak, 0.05) * 0.9  # quiet laptop mics: normalise before Whisper
    segs = transcriber.transcribe_audio(audio, prompt=course)
    return " ".join(s.text.strip() for s in segs).strip()
