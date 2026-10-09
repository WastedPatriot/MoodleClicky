"""A stand-in for the Anthropic client so tests never hit the network."""

from __future__ import annotations

import json
from types import SimpleNamespace

SAMPLE = {
    "title": "Q3 - Big-O of nested loops",
    "summary": "What is the time complexity of the two nested for-loops?",
    "steps": [
        {"text": "Look at the outer loop: it runs n times.", "label": "outer loop", "x": 200, "y": 150},
        {"text": "The inner loop also runs n times for each outer pass.", "label": "inner loop", "x": 220, "y": 180},
        {"text": "Multiply them: n x n.", "label": "", "x": -1, "y": -1},
    ],
    "answer": "O(n^2)\n```python\nfor i in range(n):\n    for j in range(n):\n        ...\n```",
    "why": "Nested loops multiply their iteration counts.",
    "check_yourself": "What if the inner loop ran only 10 times?",
}


class FakeStream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


class FakeClient:
    def __init__(self, payload=None, stop_reason="end_turn"):
        self.payload = SAMPLE if payload is None else payload
        self.stop_reason = stop_reason
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        msg = SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=2000, output_tokens=500,
                                  cache_creation_input_tokens=0, cache_read_input_tokens=0),
        )
        return FakeStream(msg)
