"""Talks to Claude: screenshot + question in, a step-by-step breakdown (with pointer targets) out."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from moodleclicky.capture import Shot
from moodleclicky.config import Settings, get_api_key

# USD per million tokens (input, output) - used only for the little cost readout.
# DeepSeek uses its peak-hour rate (off-peak is half).
PRICES = {
    "deepseek-flash": (0.30, 1.20),
    "deepseek-v4-pro": (1.32, 3.96),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-fable-5-1": (10.00, 50.00),
}

SYSTEM = """You are MoodleClicky, a friendly study buddy that lives next to the student's mouse cursor.
The student is usually on Moodle (quizzes, assignments, lecture pages) or in an editor/IDE doing coursework.
You get a screenshot of the monitor they are on. A pink ring marks where their cursor is - the thing they
are stuck on is almost always at or near that ring.

How you help:
- Find the specific question/task/error near the cursor and say in one line what it is asking.
- Teach, don't just tell. Break it into small steps a tired student can follow, one idea per step.
  Each step: 1-3 short sentences, plain English, define any jargon the first time.
- When a step is about something visible on screen (a word in the question, an option, a line of code,
  a box to fill in, a button), set its point to the pixel coordinates of that thing IN THE SCREENSHOT
  (origin top-left, image size given below). Otherwise use x = -1, y = -1.
- "why": the underlying concept in 2-4 sentences so they can do the next one alone.
- "check_yourself": one quick question that tests whether they actually understood.
- Keep the student's own words, code style and language. Code snippets short; no essays.
- If nothing study-related is visible, say so kindly in summary and give no steps.

Modes:
- breakdown: give the final answer in "answer", and the steps that get there.
- hint: do NOT give the final answer ("answer" must be ""). Steps are nudges, from gentlest to strongest.
- check: the student has written something. Mark it: steps point at what's right/wrong and why.
  "answer" = the corrected version only if they got it wrong, else "".
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "3-8 word label, e.g. 'Q4 - Big-O of nested loops'"},
        "summary": {"type": "string", "description": "One line: what the question is really asking"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "label": {"type": "string", "description": "2-4 words naming the pointed-at thing, or ''"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["text", "label", "x", "y"],
                "additionalProperties": False,
            },
        },
        "answer": {"type": "string"},
        "why": {"type": "string"},
        "check_yourself": {"type": "string"},
    },
    "required": ["title", "summary", "steps", "answer", "why", "check_yourself"],
    "additionalProperties": False,
}


@dataclass
class Step:
    text: str
    label: str = ""
    point: tuple[int, int] | None = None  # real screen coordinates


@dataclass
class Explanation:
    title: str
    summary: str
    steps: list[Step] = field(default_factory=list)
    answer: str = ""
    why: str = ""
    check_yourself: str = ""
    cost_usd: float = 0.0
    error: str = ""

    @classmethod
    def failed(cls, msg: str) -> Explanation:
        return cls(title="Hmm, that didn't work", summary=msg, error=msg)


def parse_explanation(text: str, shot: Shot | None) -> Explanation:
    data = json.loads(text)
    steps = []
    for s in data.get("steps", []):
        pt = shot.to_screen(s["x"], s["y"]) if shot and s.get("x", -1) >= 0 and s.get("y", -1) >= 0 else None
        steps.append(Step(s.get("text", "").strip(), s.get("label", "").strip(), pt))
    return Explanation(
        title=data.get("title", "").strip() or "Here's what I see",
        summary=data.get("summary", "").strip(),
        steps=steps,
        answer=data.get("answer", "").strip(),
        why=data.get("why", "").strip(),
        check_yourself=data.get("check_yourself", "").strip(),
    )


def estimate_cost(model: str, usage) -> float:
    pin, pout = PRICES.get(model, PRICES["claude-opus-5-5"])
    tokens_in = (getattr(usage, "input_tokens", 0) or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
    tokens_in += 0.1 * (getattr(usage, "cache_read_input_tokens", 0) or 0)
    return (tokens_in * pin + (getattr(usage, "output_tokens", 0) or 0) * pout) / 1_000_000


def json_example(schema: dict) -> str:
    """A tiny example object built from a JSON schema (DeepSeek's JSON mode wants one in the prompt)."""

    def ex(node):
        t = node.get("type")
        if t == "object":
            return {k: ex(v) for k, v in node.get("properties", {}).items()}
        if t == "array":
            return [ex(node.get("items", {}))]
        if t == "integer":
            return 0
        if t == "boolean":
            return False
        return node.get("description", "...")

    return json.dumps(ex(schema), ensure_ascii=False)


# ---- backends ---------------------------------------------------------------
# History is kept provider-neutral: {"role": "user"|"assistant", "text": str, "png": bytes|None, "raw": any}.
# Each backend turns it into its own wire format and returns a Reply.


class APIProblem(Exception):
    """A friendly, user-facing error from a backend."""


@dataclass
class Reply:
    text: str
    raw: object  # what to store as the assistant turn for this backend
    cost_usd: float
    stop: str  # "end", "max_tokens", "refusal"


class ClaudeBackend:
    name = "anthropic"

    def __init__(self, api_key: str = "", client=None):
        self._client = client
        self._api_key = api_key

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key or None)
        return self._client

    @staticmethod
    def to_messages(history: list[dict]) -> list[dict]:
        out = []
        for turn in history:
            if turn["role"] == "assistant":
                out.append({"role": "assistant", "content": turn.get("raw") or turn["text"]})
            elif turn.get("png"):
                b64 = base64.standard_b64encode(turn["png"]).decode("ascii")
                out.append({"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": turn["text"]},
                ]})
            else:
                out.append({"role": "user", "content": turn["text"]})
        return out

    def chat(self, settings: Settings, system: str, history: list[dict], schema: dict) -> Reply:
        import anthropic

        try:
            with self.client.beta.messages.stream(
                model=settings.model,
                max_tokens=16000,
                system=system,
                messages=self.to_messages(history),
                thinking={"type": "adaptive"},
                output_config={"effort": settings.effort, "format": {"type": "json_schema", "schema": schema}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                msg = stream.get_final_message()
        except anthropic.AuthenticationError as e:
            raise APIProblem("Your Claude API key was rejected. Open Settings and paste a new one.") from e
        except anthropic.RateLimitError as e:
            raise APIProblem("Rate limited by the API - give it a minute and try again.") from e
        except anthropic.APIConnectionError as e:
            raise APIProblem("Can't reach the internet / Anthropic API.") from e
        except anthropic.APIStatusError as e:
            raise APIProblem(f"Claude API error {e.status_code}: {e.message}") from e
        stop = {"refusal": "refusal", "max_tokens": "max_tokens"}.get(msg.stop_reason, "end")
        text = next((b.text for b in msg.content if b.type == "text"), "")
        # Keep the full content (thinking blocks included) so follow-ups stay valid.
        return Reply(text, msg.content, estimate_cost(settings.model, msg.usage), stop)


class DeepSeekHTTP:
    """Minimal client for DeepSeek's OpenAI-compatible /chat/completions (stdlib only)."""

    URL = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def chat(self, payload: dict) -> dict:
        req = urllib.request.Request(
            self.URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:  # nosec B310 - fixed https URL
            return json.loads(resp.read().decode("utf-8"))


class DeepSeekBackend:
    name = "deepseek"
    EFFORT = {"low": "low", "medium": "high", "high": "max"}

    def __init__(self, api_key: str = "", client=None):
        self._client = client or DeepSeekHTTP(api_key)

    @staticmethod
    def to_messages(system: str, history: list[dict]) -> list[dict]:
        out = [{"role": "system", "content": system}]
        for turn in history:
            if turn["role"] == "assistant":
                out.append({"role": "assistant", "content": turn["text"]})
            elif turn.get("png"):
                b64 = base64.standard_b64encode(turn["png"]).decode("ascii")
                out.append({"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
                    {"type": "text", "text": turn["text"]},
                ]})
            else:
                out.append({"role": "user", "content": turn["text"]})
        return out

    def chat(self, settings: Settings, system: str, history: list[dict], schema: dict) -> Reply:
        system = (
            f"{system}\n\nReply with a single json object only (no markdown fences) with exactly these keys, "
            f"following this JSON schema:\n{json.dumps(schema)}\nExample shape:\n{json_example(schema)}"
        )
        payload = {
            "model": settings.deepseek_model,
            "messages": self.to_messages(system, history),
            "response_format": {"type": "json_object"},
            "max_tokens": 16000,
            "thinking": {"type": "enabled"},
            "reasoning_effort": self.EFFORT.get(settings.effort, "high"),
        }
        try:
            data = self._client.chat(payload)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise APIProblem("Your DeepSeek API key was rejected. Open Settings and paste a new one.") from e
            if e.code == 402:
                raise APIProblem("DeepSeek says the account is out of credit - top up at platform.deepseek.com.") from e
            if e.code == 429:
                raise APIProblem("DeepSeek is rate limiting - give it a minute and try again.") from e
            detail = e.read().decode("utf-8", "replace")[:200] if hasattr(e, "read") else ""
            raise APIProblem(f"DeepSeek API error {e.code}. {detail}".strip()) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise APIProblem("Can't reach the internet / DeepSeek API.") from e
        try:
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as e:
            raise APIProblem("Got an unexpected reply from DeepSeek - try again.") from e
        stop = {"length": "max_tokens", "content_filter": "refusal"}.get(choice.get("finish_reason"), "end")
        usage = data.get("usage") or {}
        pin, pout = PRICES.get(settings.deepseek_model, PRICES["deepseek-flash"])
        cost = ((usage.get("prompt_tokens") or 0) * pin + (usage.get("completion_tokens") or 0) * pout) / 1e6
        return Reply(text, None, cost, stop)


def make_backend(settings: Settings, claude_client=None, deepseek_client=None):
    if settings.provider == "deepseek":
        return DeepSeekBackend(get_api_key("deepseek"), deepseek_client)
    return ClaudeBackend(get_api_key("anthropic"), claude_client)


def has_key(settings: Settings) -> bool:
    return bool(get_api_key(settings.provider))



class Tutor:
    """One conversation per hotkey press; follow-ups continue it (append-only history)."""

    def __init__(self, settings: Settings, client=None, deepseek_client=None):
        self.settings = settings
        self._claude_client = client  # injected fakes for tests
        self._deepseek_client = deepseek_client
        self._backend = None
        self.history: list[dict] = []
        self.shot: Shot | None = None
        self.total_cost = 0.0

    @property
    def ready(self) -> bool:
        injected = self._deepseek_client if self.settings.provider == "deepseek" else self._claude_client
        return injected is not None or has_key(self.settings)

    def reset_backend(self) -> None:
        """Call after settings/keys change; the next question builds a fresh client."""
        self._backend = None

    @property
    def backend(self):
        if self._backend is None or self._backend.name != self.settings.provider:
            self._backend = make_backend(self.settings, self._claude_client, self._deepseek_client)
        return self._backend

    def _mode_line(self, mode: str) -> str:
        line = f"Mode: {mode}."
        if self.settings.course_context:
            line += f" Course context: {self.settings.course_context}."
        return line

    def ask(self, shot: Shot, question: str, mode: str) -> Explanation:
        self.shot = shot
        self._backend = None if self._backend and self._backend.name != self.settings.provider else self._backend
        ask = question.strip() or "I'm stuck on the thing at my cursor. Help me understand it."
        self.history = [{
            "role": "user",
            "png": shot.png,
            "text": (
                f"Screenshot is {shot.width}x{shot.height}px. Cursor ring at {shot.cursor}.\n"
                f"{self._mode_line(mode)}\n\nStudent: {ask}"
            ),
        }]
        return self._run()

    def follow_up(self, text: str, mode: str) -> Explanation:
        if not self.history:
            return Explanation.failed("Press the hotkey first so I can see your screen.")
        self.history.append({"role": "user", "text": f"{self._mode_line(mode)}\n\nStudent: {text.strip()}"})
        return self._run()

    def _run(self) -> Explanation:
        try:
            reply = self.backend.chat(self.settings, SYSTEM, self.history, SCHEMA)
        except APIProblem as e:
            self.history.pop()  # let them retry the same question
            return Explanation.failed(str(e))
        self.total_cost += reply.cost_usd
        self.history.append({"role": "assistant", "text": reply.text, "raw": reply.raw})
        if reply.stop == "refusal":
            return Explanation.failed("The AI declined to help with this one.")
        try:
            exp = parse_explanation(reply.text, self.shot)
        except (ValueError, KeyError, TypeError):
            if reply.stop == "max_tokens":
                return Explanation.failed("The answer got cut off - try a narrower question.")
            return Explanation.failed("Got a garbled reply - try again.")
        exp.cost_usd = reply.cost_usd
        return exp
