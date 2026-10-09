"""Turn a transcript into notes: lecture notes, a group-meeting plan, or a quick "what did I miss?"."""

from __future__ import annotations

import json

from moodleclicky.brain import APIProblem, make_backend
from moodleclicky.config import Settings
from moodleclicky.lecture.transcribe import Segment, fmt_time

_STR_LIST = {"type": "array", "items": {"type": "string"}}


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


LECTURE_SCHEMA = _obj({
    "title": {"type": "string", "description": "Topic of the lecture, 3-8 words"},
    "tl_dr": {"type": "string", "description": "2-3 sentence summary"},
    "key_points": _STR_LIST,
    "concepts": {"type": "array", "items": _obj({"term": {"type": "string"}, "meaning": {"type": "string"}})},
    "examples": _STR_LIST,
    "marked_moments": {"type": "array", "items": _obj({"time": {"type": "string"},
                                                       "why_it_matters": {"type": "string"}})},
    "to_do": _STR_LIST,  # readings, deadlines, things the lecturer said to do
    "questions_to_review": _STR_LIST,
})

MEETING_SCHEMA = _obj({
    "title": {"type": "string"},
    "tl_dr": {"type": "string"},
    "decisions": _STR_LIST,
    "action_items": {"type": "array", "items": _obj({"who": {"type": "string"}, "task": {"type": "string"},
                                                     "due": {"type": "string"}})},
    "my_tasks": _STR_LIST,
    "plan": {"type": "array", "items": _obj({"step": {"type": "string"}, "owner": {"type": "string"},
                                             "when": {"type": "string"}})},
    "open_questions": _STR_LIST,
    "risks": _STR_LIST,
})

CATCHUP_SCHEMA = _obj({
    "now_discussing": {"type": "string", "description": "One line: what's being talked about right now"},
    "what_you_missed": _STR_LIST,
    "for_you": {**_STR_LIST, "description": "Anything aimed at the student: their name, a question to them, "
                                             "a task, a deadline. Empty if none."},
    "say_this": {"type": "string", "description": "If they're put on the spot: a sensible thing to say/ask. "
                                                  "Empty if not needed."},
})

SYSTEM = """You turn a rough live speech-to-text transcript into notes for a busy university student
(a parent who sometimes zones out). The transcript has [mm:ss] timestamps and may contain recognition
mistakes - fix obvious ones silently, never invent content that isn't there.
Write short, plain-English bullet points. Lines marked ⭐ are moments the student flagged as important -
make sure they're covered and listed in marked_moments (if that field exists)."""


def transcript_text(segments: list[Segment], markers: list[float] | None = None, since: float = 0.0) -> str:
    marks = sorted(markers or [])
    lines = []
    for s in segments:
        if s.end < since:
            continue
        star = "⭐ " if any(s.start - 15 <= m <= s.end + 5 for m in marks) else ""
        lines.append(f"[{fmt_time(s.start)}] {star}{s.text}")
    return "\n".join(lines)


def _ask(settings: Settings, prompt: str, schema: dict, backend=None) -> dict:
    backend = backend or make_backend(settings)
    reply = backend.chat(settings, SYSTEM, [{"role": "user", "text": prompt}], schema)
    if reply.stop == "refusal":
        raise APIProblem("The AI declined to summarise this.")
    try:
        data = json.loads(reply.text)
    except ValueError as e:
        raise APIProblem("Got a garbled reply - try again." if reply.stop != "max_tokens"
                         else "The notes got cut off - try again.") from e
    data["_cost_usd"] = reply.cost_usd
    return data


def make_notes(settings: Settings, kind: str, segments: list[Segment], markers: list[float],
               backend=None) -> dict:
    text = transcript_text(segments, markers)
    if not text.strip():
        raise APIProblem("Nothing was transcribed yet - is the right audio source on?")
    ctx = f"Course: {settings.course_context}. " if settings.course_context else ""
    if kind == "meeting":
        me = settings.your_name or "the student"
        prompt = (f"{ctx}This is a group project meeting. The student is called {me}. Pull out decisions, "
                  f"who is doing what, {me}'s own tasks (my_tasks), and turn it into a simple step-by-step plan."
                  f"\n\nTranscript:\n{text}")
        return _ask(settings, prompt, MEETING_SCHEMA, backend)
    prompt = f"{ctx}This is a lecture. Make revision notes.\n\nTranscript:\n{text}"
    return _ask(settings, prompt, LECTURE_SCHEMA, backend)


def catch_up(settings: Settings, kind: str, segments: list[Segment], now: float, minutes: int = 5,
             backend=None) -> dict:
    since = max(0.0, now - minutes * 60)
    recent = transcript_text(segments, since=since)
    if not recent.strip():
        raise APIProblem(f"Nothing was said in the last {minutes} minutes (or audio isn't coming through).")
    earlier = transcript_text(segments)[-6000:]  # a bit of context
    me = settings.your_name or "the student"
    prompt = (f"The student ({me}) wasn't paying attention for the last {minutes} minutes of this {kind}. "
              f"Catch them up fast.\n\nEarlier context (may be cut):\n{earlier}\n\n"
              f"LAST {minutes} MINUTES:\n{recent}")
    return _ask(settings, prompt, CATCHUP_SCHEMA, backend)


# ---- Markdown -------------------------------------------------------------

def _bullets(items) -> list[str]:
    return [f"- {i}" for i in items if str(i).strip()]


def notes_markdown(kind: str, data: dict, when: str, duration: str) -> str:
    out = [f"# {data.get('title') or ('Meeting' if kind == 'meeting' else 'Lecture')}",
           f"*{when} · {duration} · {'group meeting' if kind == 'meeting' else 'lecture'}*", ""]
    if data.get("tl_dr"):
        out += [f"> {data['tl_dr']}", ""]

    def section(title, lines):
        if lines:
            out.extend([f"## {title}", *lines, ""])

    if kind == "meeting":
        section("My tasks", [f"- [ ] {t}" for t in data.get("my_tasks", [])])
        section("Decisions", _bullets(data.get("decisions", [])))
        section("Who's doing what", [f"- **{a.get('who') or '?'}**: {a.get('task')}"
                                     + (f" *(due {a['due']})*" if a.get("due") else "")
                                     for a in data.get("action_items", [])])
        section("Plan", [f"{i}. {p.get('step')}" + (f" - {p['owner']}" if p.get("owner") else "")
                         + (f" ({p['when']})" if p.get("when") else "")
                         for i, p in enumerate(data.get("plan", []), 1)])
        section("Open questions", _bullets(data.get("open_questions", [])))
        section("Risks", _bullets(data.get("risks", [])))
    else:
        section("Key points", _bullets(data.get("key_points", [])))
        section("Concepts", [f"- **{c.get('term')}**: {c.get('meaning')}" for c in data.get("concepts", [])])
        section("Examples", _bullets(data.get("examples", [])))
        section("⭐ Moments you marked", [f"- `{m.get('time')}` {m.get('why_it_matters')}"
                                          for m in data.get("marked_moments", [])])
        section("To do", [f"- [ ] {t}" for t in data.get("to_do", [])])
        section("Test yourself", _bullets(data.get("questions_to_review", [])))
    return "\n".join(out).rstrip() + "\n"


def catchup_text(data: dict) -> str:
    out = []
    if data.get("now_discussing"):
        out += [f"Right now: {data['now_discussing']}", ""]
    if data.get("for_you"):
        out += ["For YOU:", *[f"• {x}" for x in data["for_you"]], ""]
    if data.get("what_you_missed"):
        out += ["You missed:", *[f"• {x}" for x in data["what_you_missed"]], ""]
    if data.get("say_this"):
        out += [f"If asked, you could say: “{data['say_this']}”"]
    return "\n".join(out).strip()
