"""Record the microphone and/or the computer's own audio (WASAPI loopback) into 16 kHz mono WAV chunks.

Built to keep going for a 2-hour lecture: each source runs in its own thread and a wall-clock mixer
pads any source that goes quiet (loopback delivers nothing while no sound is playing), so one dead
source never stalls the recording. Chunks hit the disk every `chunk_secs`, so a crash loses seconds.
"""

from __future__ import annotations

import threading
import time
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

RATE = 16000
BLOCK = 1600  # 0.1 s


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def read_wav(path: Path) -> np.ndarray:
    """Any 16-bit PCM WAV -> 16 kHz mono float32 (what Whisper wants)."""
    with wave.open(str(path), "rb") as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"{path.name}: only 16-bit WAV is supported")
    data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32767
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    if rate != RATE and len(data):
        n = int(len(data) * RATE / rate)
        data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data).astype(np.float32)
    return data


class Source:
    """One capture thread. `open_recorder` returns a context manager with .record(numframes) -> ndarray."""

    def __init__(self, name: str, open_recorder: Callable[[], object]):
        self.name = name
        self.open_recorder = open_recorder
        self.buf = np.zeros(0, dtype=np.float32)
        self.lock = threading.Lock()
        self.error = ""
        self.alive = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name=f"rec-{self.name}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def take(self, n: int) -> np.ndarray:
        """Up to n samples (padded with silence). Drops backlog over 1 s so sources stay in sync."""
        with self.lock:
            if len(self.buf) > RATE:
                self.buf = self.buf[-RATE // 2:]
            out, self.buf = self.buf[:n], self.buf[n:]
        if len(out) < n:
            out = np.concatenate([out, np.zeros(n - len(out), dtype=np.float32)])
        return out

    def _run(self) -> None:
        from moodleclicky.winutil import com_init

        com_init()
        while not self._stop.is_set():
            try:
                with self.open_recorder() as rec:
                    self.alive, self.error = True, ""
                    while not self._stop.is_set():
                        data = np.asarray(rec.record(numframes=BLOCK), dtype=np.float32)
                        if data.ndim > 1:
                            data = data.mean(axis=1)
                        with self.lock:
                            self.buf = np.concatenate([self.buf, data])
            except Exception as e:  # device unplugged / changed: retry after a pause
                self.alive, self.error = False, str(e) or type(e).__name__
                self._stop.wait(2.0)
        self.alive = False


def soundcard_sources(mic: bool, system: bool) -> list[Source]:
    """Real devices via the `soundcard` package (Windows WASAPI, also macOS/Linux)."""
    import soundcard as sc

    sources = []
    if mic:
        sources.append(Source("mic", lambda: sc.default_microphone().recorder(samplerate=RATE, channels=1,
                                                                              blocksize=BLOCK)))
    if system:
        def loopback():
            spk = sc.default_speaker()
            dev = sc.get_microphone(id=str(spk.name), include_loopback=True)
            return dev.recorder(samplerate=RATE, channels=1, blocksize=BLOCK)

        sources.append(Source("computer audio", loopback))
    return sources


class Recorder:
    def __init__(self, out_dir: Path, sources: list[Source], chunk_secs: int = 30,
                 on_chunk: Callable[[Path, float], None] | None = None):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.sources = sources
        self.chunk_secs = chunk_secs
        self.on_chunk = on_chunk or (lambda p, t: None)
        self.level = 0.0  # 0..1 for a VU meter
        self.recorded_secs = 0.0  # audio time (excludes pauses)
        self.paused = False
        self._chunk: list[np.ndarray] = []
        self._chunk_start = 0.0
        self._index = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def status(self) -> str:
        bits = []
        for s in self.sources:
            bits.append(f"{s.name}: {'ok' if s.alive else ('error - ' + s.error if s.error else 'starting')}")
        return " · ".join(bits)

    def start(self) -> None:
        for s in self.sources:
            s.start()
        self._thread = threading.Thread(target=self._mix, name="rec-mixer", daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def stop(self) -> None:
        self._stop.set()
        for s in self.sources:
            s.stop()
        if self._thread:
            self._thread.join(timeout=5)
        self._flush()

    def _mix(self) -> None:
        tick = BLOCK / RATE
        next_t = time.monotonic()
        while not self._stop.is_set():
            next_t += tick
            delay = next_t - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            elif delay < -1.0:
                next_t = time.monotonic()  # we fell behind (sleep/hibernate) - resync, don't spin
            blocks = [s.take(BLOCK) for s in self.sources]
            if self.paused or not blocks:
                self.level = 0.0
                continue
            mixed = np.clip(np.sum(blocks, axis=0), -1.0, 1.0)
            self.level = float(min(1.0, np.sqrt(np.mean(mixed ** 2)) * 6))
            self._chunk.append(mixed)
            self.recorded_secs += tick
            if len(self._chunk) * BLOCK >= self.chunk_secs * RATE:
                self._flush()

    def _flush(self) -> None:
        if not self._chunk:
            return
        samples = np.concatenate(self._chunk)
        self._chunk = []
        path = self.out_dir / f"chunk_{self._index:04d}.wav"
        self._index += 1
        start = self._chunk_start
        self._chunk_start += len(samples) / RATE
        write_wav(path, samples)
        self.on_chunk(path, start)
