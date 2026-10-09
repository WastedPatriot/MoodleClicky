"""Local speech-to-text with faster-whisper (runs on your CPU - free, and audio never leaves the PC)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from moodleclicky.config import data_dir


@dataclass
class Segment:
    start: float  # seconds from the start of the recording
    end: float
    text: str


def fmt_time(secs: float) -> str:
    secs = int(max(0, secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# Whisper sometimes "hears" these in silence/noise - drop them.
_HALLUCINATIONS = {"thank you.", "thanks for watching!", "thank you for watching.", "you", "bye.", "."}


def clean(segments: list[Segment]) -> list[Segment]:
    out = []
    for s in segments:
        t = s.text.strip()
        if not t or t.lower() in _HALLUCINATIONS:
            continue
        if out and t == out[-1].text:  # stuck repeating
            continue
        out.append(Segment(s.start, s.end, t))
    return out


class WhisperTranscriber:
    def __init__(self, model_name: str = "small.en", on_status=None):
        self.model_name = model_name
        self.on_status = on_status or (lambda msg: None)
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        self.on_status(f"Loading speech model '{self.model_name}' (first time downloads it)…")
        root = data_dir() / "models"
        root.mkdir(parents=True, exist_ok=True)
        self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8", download_root=str(root))
        self.on_status("Speech model ready")

    def transcribe(self, wav: Path, offset: float = 0.0, prompt: str = "") -> list[Segment]:
        from moodleclicky.lecture.audio import read_wav

        self.load()
        audio = read_wav(wav)  # decode ourselves: no ffmpeg/PyAV needed
        if len(audio) < 1600:
            return []
        segments, _info = self._model.transcribe(
            audio,
            beam_size=3,
            vad_filter=True,  # skips silence -> faster, fewer hallucinations
            condition_on_previous_text=False,
            initial_prompt=prompt[-400:] or None,  # last bit of transcript keeps names/terms consistent
        )
        return clean([Segment(offset + s.start, offset + s.end, s.text) for s in segments])
