import json
import os
import shutil
import subprocess  # nosec B404 - test helper
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("MOODLECLICKY_HOME", tempfile.mkdtemp())

import numpy as np
import pytest

from moodleclicky.brain import APIProblem, Reply
from moodleclicky.config import Settings
from moodleclicky.lecture import summarise
from moodleclicky.lecture.audio import RATE, Recorder, Source, read_wav, write_wav
from moodleclicky.lecture.session import Session, recent_sessions
from moodleclicky.lecture.transcribe import Segment, clean, fmt_time


class ToneRecorder:
    """Stands in for a soundcard recorder: returns a 440 Hz tone in real time."""

    def __init__(self, amp=0.3):
        self.amp = amp
        self.t = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def record(self, numframes):
        time.sleep(numframes / RATE)
        x = np.arange(self.t, self.t + numframes) / RATE
        self.t += numframes
        return (self.amp * np.sin(2 * np.pi * 440 * x)).astype(np.float32)


class SilentForever:
    """Like WASAPI loopback with nothing playing: record() never returns data."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def record(self, numframes):
        time.sleep(3600)


def test_wav_roundtrip_and_resample(tmp_path):
    tone = (0.5 * np.sin(np.linspace(0, 100, 8000))).astype(np.float32)
    write_wav(tmp_path / "a.wav", tone)
    back = read_wav(tmp_path / "a.wav")
    assert len(back) == 8000 and np.max(np.abs(back - tone)) < 1e-3
    import wave

    with wave.open(str(tmp_path / "b.wav"), "wb") as w:  # 44.1 kHz stereo -> 16 kHz mono
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(np.zeros(44100 * 2, dtype="<i2").tobytes())
    assert abs(len(read_wav(tmp_path / "b.wav")) - 16000) <= 1


def test_recorder_mixes_and_survives_a_silent_source(tmp_path):
    chunks = []
    srcs = [Source("mic", ToneRecorder), Source("computer audio", SilentForever)]
    rec = Recorder(tmp_path, srcs, chunk_secs=1, on_chunk=lambda p, t: chunks.append((p, t)))
    rec.start()
    time.sleep(2.6)
    assert rec.level > 0.1
    rec.pause()
    time.sleep(0.5)
    rec.resume()
    time.sleep(0.3)
    rec.stop()
    assert len(chunks) >= 2, chunks  # the silent loopback didn't stall anything
    assert chunks[0][1] == 0.0 and chunks[1][1] == 1.0
    audio = read_wav(chunks[0][0])
    assert len(audio) == RATE and np.sqrt(np.mean(audio ** 2)) > 0.1
    assert 2.5 < rec.recorded_secs < 3.4  # pause time not counted


def test_recorder_retries_a_broken_device(tmp_path):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("device unplugged")
        return ToneRecorder()

    src = Source("mic", flaky)
    rec = Recorder(tmp_path, [src], chunk_secs=1)
    rec.start()
    time.sleep(0.3)
    assert "unplugged" in rec.status()
    time.sleep(2.5)
    assert src.alive and calls["n"] == 2
    rec.stop()


def test_clean_drops_hallucinations_and_repeats():
    segs = [Segment(0, 1, " Thank you."), Segment(1, 2, "Hello"), Segment(2, 3, "Hello"), Segment(3, 4, "World")]
    assert [s.text for s in clean(segs)] == ["Hello", "World"]
    assert fmt_time(75) == "01:15" and fmt_time(3725) == "1:02:05"


class FakeChunkRecorder:
    """Pretends to record: emits three 'chunks' then stops."""

    def __init__(self, folder, on_chunk):
        self.folder, self.on_chunk = Path(folder), on_chunk
        self.folder.mkdir(parents=True, exist_ok=True)
        self.recorded_secs = 0.0

    def start(self):
        for i in range(3):
            p = self.folder / f"chunk_{i:04d}.wav"
            write_wav(p, np.zeros(1600, dtype=np.float32))
            self.recorded_secs += 30
            self.on_chunk(p, i * 30.0)

    def pause(self):
        pass

    def resume(self):
        pass

    def stop(self):
        pass


class FakeTranscriber:
    lines = ["Today: binary search trees.", "Coursework two is due Friday.", "Dominic, can you do the UML?"]

    def transcribe(self, wav, offset, prompt=""):
        i = int(offset // 30)
        return [Segment(offset, offset + 10, self.lines[i])]


def test_session_records_transcribes_and_persists():
    s = Session(Settings(), "meeting", recorder_factory=FakeChunkRecorder, transcriber=FakeTranscriber())
    s.start()
    s.mark()
    s.stop()
    assert s.wait(10) and s.state == "done"
    assert [x.text for x in s.segments] == FakeTranscriber.lines
    assert not list((s.folder / "audio").glob("*.wav"))  # audio deleted once transcribed
    text = (s.folder / "transcript.md").read_text(encoding="utf-8")
    assert "[01:00] Dominic, can you do the UML?" in text
    loaded = Session.load(s.folder, Settings())
    assert loaded.kind == "meeting" and len(loaded.segments) == 3 and loaded.markers == [90.0]
    assert s.folder in recent_sessions()


class FakeBackend:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def chat(self, settings, system, history, schema):
        self.prompts.append(history[0]["text"])
        assert set(schema["required"]) <= set(self.payload) | {"_cost_usd"}
        return Reply(json.dumps(self.payload), None, 0.002, "end")


SEGS = [Segment(i * 60, i * 60 + 30, t) for i, t in enumerate(FakeTranscriber.lines)]


def test_lecture_notes_markdown():
    data = {"title": "Binary search trees", "tl_dr": "BSTs keep things sorted.", "key_points": ["O(log n) search"],
            "concepts": [{"term": "BST", "meaning": "left < node < right"}], "examples": [],
            "marked_moments": [{"time": "01:00", "why_it_matters": "deadline"}], "to_do": ["CW2 by Friday"],
            "questions_to_review": ["Why can a BST degrade to O(n)?"]}
    fb = FakeBackend(data)
    notes = summarise.make_notes(Settings(course_context="COMP1234"), "lecture", SEGS, [65.0], backend=fb)
    assert "⭐ Coursework two" in fb.prompts[0] and "COMP1234" in fb.prompts[0]
    md = summarise.notes_markdown("lecture", notes, "Thu 9 Oct", "45 min")
    assert md.startswith("# Binary search trees") and "- [ ] CW2 by Friday" in md and "**BST**" in md


def test_meeting_notes_pull_out_my_tasks():
    data = {"title": "Group project", "tl_dr": "Split the work.", "decisions": ["Use Java"],
            "action_items": [{"who": "Dominic", "task": "UML diagram", "due": "Mon"}], "my_tasks": ["UML diagram"],
            "plan": [{"step": "Draft UML", "owner": "Dominic", "when": "Mon"}], "open_questions": [], "risks": []}
    fb = FakeBackend(data)
    notes = summarise.make_notes(Settings(your_name="Dominic"), "meeting", SEGS, [], backend=fb)
    assert "called Dominic" in fb.prompts[0]
    md = summarise.notes_markdown("meeting", notes, "today", "20 min")
    assert "## My tasks\n- [ ] UML diagram" in md and "1. Draft UML - Dominic (Mon)" in md


def test_catch_up_only_sends_recent_minutes():
    data = {"now_discussing": "who does UML", "what_you_missed": ["CW2 due Friday"],
            "for_you": ["You were asked to do the UML"], "say_this": "Yes, I'll take the UML."}
    fb = FakeBackend(data)
    out = summarise.catch_up(Settings(), "meeting", SEGS, now=160, minutes=1, backend=fb)
    assert fb.prompts[0].endswith("LAST 1 MINUTES:\n[02:00] Dominic, can you do the UML?")
    txt = summarise.catchup_text(out)
    assert txt.startswith("Right now: who does UML") and "For YOU:" in txt
    with pytest.raises(APIProblem):
        summarise.catch_up(Settings(), "lecture", SEGS, now=5000, minutes=1, backend=fb)
    with pytest.raises(APIProblem):
        summarise.make_notes(Settings(), "lecture", [], [], backend=fb)


@pytest.mark.skipif(not shutil.which("espeak-ng") or os.environ.get("MC_SKIP_WHISPER") == "1",
                    reason="needs espeak-ng to synthesise speech")
def test_real_whisper_transcribes_speech(tmp_path):
    pytest.importorskip("faster_whisper")
    from moodleclicky.lecture.transcribe import WhisperTranscriber

    wav = tmp_path / "speech.wav"
    subprocess.run(["espeak-ng", "-s", "140", "-w", str(wav),  # nosec B603 B607
                    "Good morning everyone. Today we will talk about databases."], check=True)
    segs = WhisperTranscriber("tiny.en").transcribe(wav, offset=120)
    text = " ".join(s.text.lower() for s in segs)
    assert segs and segs[0].start >= 120
    assert "morning" in text and "everyone" in text
