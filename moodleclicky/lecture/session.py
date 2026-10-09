"""One recording session: recorder -> 30 s WAV chunks -> background transcription -> transcript on disk.

Everything is written as it happens (session.json + transcript.md), so if the laptop dies mid-lecture
you still have the transcript up to that point and can make notes from it later.
"""

from __future__ import annotations

import json
import queue
import threading
from datetime import datetime
from pathlib import Path

from moodleclicky.config import Settings, data_dir
from moodleclicky.lecture.transcribe import Segment, fmt_time


def sessions_dir() -> Path:
    d = data_dir() / "lectures"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Session:
    def __init__(self, settings: Settings, kind: str = "lecture", folder: Path | None = None,
                 recorder_factory=None, transcriber=None, on_update=None):
        self.settings = settings
        self.kind = kind if kind in ("lecture", "meeting") else "lecture"
        self.started = datetime.now()
        self.folder = folder or sessions_dir() / f"{self.started:%Y-%m-%d_%H%M}_{self.kind}"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.segments: list[Segment] = []
        self.markers: list[float] = []
        self.state = "idle"  # idle | recording | paused | finishing | done
        self.status = ""
        self.backlog = 0  # chunks waiting to be transcribed
        self.duration = 0.0
        self.on_update = on_update or (lambda: None)
        self._recorder_factory = recorder_factory
        self._transcriber = transcriber
        self.recorder = None
        self._jobs: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()
        self._worker: threading.Thread | None = None

    # ---- lifecycle -----------------------------------------------------
    def start(self) -> None:
        if self._transcriber is None:
            from moodleclicky.lecture.transcribe import WhisperTranscriber

            self._transcriber = WhisperTranscriber(self.settings.whisper_model, on_status=self._set_status)
        if self._recorder_factory is None:
            from moodleclicky.lecture.audio import Recorder, soundcard_sources

            def factory(folder, on_chunk):
                srcs = soundcard_sources(self.settings.record_mic, self.settings.record_system)
                if not srcs:
                    raise RuntimeError("Turn on the microphone and/or computer audio in Settings.")
                return Recorder(folder, srcs, on_chunk=on_chunk)

            self._recorder_factory = factory
        self.recorder = self._recorder_factory(self.folder / "audio", self._chunk_ready)
        self._worker = threading.Thread(target=self._transcribe_loop, name="transcriber", daemon=True)
        self._worker.start()
        self.recorder.start()
        self.state = "recording"
        self._save()
        self._set_status("Recording")

    def pause(self) -> None:
        if self.recorder and self.state == "recording":
            self.recorder.pause()
            self.state = "paused"
            self.on_update()

    def resume(self) -> None:
        if self.recorder and self.state == "paused":
            self.recorder.resume()
            self.state = "recording"
            self.on_update()

    def stop(self) -> None:
        """Stop recording; transcription of the last chunks carries on in the background."""
        if self.state not in ("recording", "paused"):
            return
        self.state = "finishing"
        self.duration = self.elapsed()
        self.recorder.stop()  # flushes the final partial chunk
        self._jobs.put(None)
        self._set_status("Finishing the transcript…")

    def wait(self, timeout: float | None = None) -> bool:
        if self._worker:
            self._worker.join(timeout)
            return not self._worker.is_alive()
        return True

    def mark(self) -> float:
        t = self.elapsed()
        with self._lock:
            self.markers.append(t)
        self._save()
        self.on_update()
        return t

    def elapsed(self) -> float:
        if self.recorder is not None and self.state in ("recording", "paused"):
            return self.recorder.recorded_secs
        return self.duration or (self.segments[-1].end if self.segments else 0.0)

    # ---- worker --------------------------------------------------------
    def _chunk_ready(self, path: Path, offset: float) -> None:
        self.backlog += 1
        self._jobs.put((path, offset))

    def _transcribe_loop(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                break
            path, offset = job
            try:
                prompt = " ".join(s.text for s in self.segments[-8:])
                if self.settings.course_context:
                    prompt = f"{self.settings.course_context}. {prompt}"
                new = self._transcriber.transcribe(path, offset, prompt)
                with self._lock:
                    self.segments.extend(new)
                self._append_transcript(new)
                path.unlink(missing_ok=True)  # audio no longer needed once transcribed
            except Exception as e:  # keep the WAV so it can be retried later
                self._set_status(f"Couldn't transcribe a chunk ({e}) - audio kept in {path.parent}")
            finally:
                self.backlog = max(0, self.backlog - 1)
                self._save()
                self.on_update()
        self.state = "done"
        self._save()
        self._set_status("Transcript complete")

    # ---- persistence ---------------------------------------------------
    def _append_transcript(self, segs: list[Segment]) -> None:
        path = self.folder / "transcript.md"
        new_file = not path.exists()
        with path.open("a", encoding="utf-8") as f:
            if new_file:
                f.write(f"# Transcript - {self.kind} - {self.started:%A %d %B %Y, %H:%M}\n\n")
            for s in segs:
                f.write(f"[{fmt_time(s.start)}] {s.text}\n")

    def _save(self) -> None:
        with self._lock:
            data = {
                "kind": self.kind,
                "started": self.started.isoformat(timespec="seconds"),
                "state": self.state,
                "duration": self.elapsed(),
                "markers": self.markers,
                "segments": [[s.start, s.end, s.text] for s in self.segments],
            }
        with self._save_lock:  # recorder, transcriber and UI threads all save
            tmp = self.folder / "session.json.tmp"
            try:
                tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                tmp.replace(self.folder / "session.json")
            except OSError as e:  # disk full / antivirus lock: keep recording, retry on next save
                self.status = f"Couldn't save session file: {e}"

    def _set_status(self, msg: str) -> None:
        self.status = msg
        self.on_update()

    @classmethod
    def load(cls, folder: Path, settings: Settings) -> Session:
        data = json.loads((folder / "session.json").read_text(encoding="utf-8"))
        s = cls(settings, data.get("kind", "lecture"), folder=folder)
        s.started = datetime.fromisoformat(data["started"])
        s.segments = [Segment(a, b, t) for a, b, t in data.get("segments", [])]
        s.markers = list(data.get("markers", []))
        s.duration = float(data.get("duration") or 0)
        s.state = "done"
        return s

    def save_notes(self, markdown: str) -> Path:
        path = self.folder / "notes.md"
        path.write_text(markdown, encoding="utf-8")
        return path


def recent_sessions(limit: int = 15) -> list[Path]:
    dirs = [d for d in sessions_dir().iterdir() if (d / "session.json").exists()]
    return sorted(dirs, reverse=True)[:limit]
