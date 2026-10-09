import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["MOODLECLICKY_HOME"] = tempfile.mkdtemp()

from PIL import Image

from fakes import SAMPLE, FakeClient
from moodleclicky import notes
from moodleclicky.brain import Tutor, estimate_cost, parse_explanation
from moodleclicky.capture import build_shot, monitor_for
from moodleclicky.config import Settings


def make_shot(w=3136, h=1764, left=1920, top=0):
    return build_shot(Image.new("RGB", (w, h), "white"), left, top, (left + 400, top + 300), 1568)


def test_shot_scales_and_maps_back():
    shot = make_shot()
    assert shot.width == 1568 and shot.height == 882
    assert abs(shot.scale - 0.5) < 1e-9
    assert shot.cursor == (200, 150)
    assert shot.to_screen(200, 150) == (2320, 300)  # back on the second monitor
    assert shot.to_screen(-1, -1) is None
    assert shot.to_screen(5000, 10) is None
    assert shot.image[:3] == b"\xff\xd8\xff" and shot.media_type == "image/jpeg"


def test_small_screens_are_not_upscaled():
    shot = build_shot(Image.new("RGB", (800, 600)), 0, 0, (10, 10), 1568)
    assert shot.scale == 1.0 and (shot.width, shot.height) == (800, 600)


def test_monitor_for_picks_the_right_screen():
    mons = [{"left": 0, "top": 0, "width": 3840, "height": 1080},
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 1920, "top": 0, "width": 1920, "height": 1080}]
    assert monitor_for(mons, 2500, 10)["left"] == 1920
    assert monitor_for(mons, 100, 10)["left"] == 0
    assert monitor_for(mons, -50, -50)["left"] == 0  # off-screen -> primary


def test_parse_explanation_maps_points():
    import json

    exp = parse_explanation(json.dumps(SAMPLE), make_shot())
    assert exp.title.startswith("Q3")
    assert exp.steps[0].point == (1920 + 400, 300)
    assert exp.steps[2].point is None
    assert "O(n^2)" in exp.answer


def test_tutor_ask_and_follow_up_keep_history():
    s = Settings()
    fake = FakeClient()
    t = Tutor(s, client=fake)
    exp = t.ask(make_shot(), "", "hint")
    assert not exp.error and len(exp.steps) == 3
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "low"
    assert call["fallbacks"] == "default"
    content = call["messages"][0]["content"]
    assert content[0]["type"] == "image" and "Mode: hint." in content[1]["text"]
    assert exp.cost_usd > 0

    exp2 = t.follow_up("why n squared?", "breakdown")
    assert not exp2.error
    msgs = fake.calls[1]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"][0].type == "thinking"  # full content kept, not just text
    assert msgs[0]["content"][0]["type"] == "image"
    assert t.total_cost > exp.cost_usd


def test_follow_up_without_screenshot_is_friendly():
    exp = Tutor(Settings(), client=FakeClient()).follow_up("hi", "hint")
    assert exp.error


def test_garbled_and_refused_replies():
    assert Tutor(Settings(), client=FakeClient(payload="not json")).ask(make_shot(), "", "hint").error
    assert Tutor(Settings(), client=FakeClient(stop_reason="refusal")).ask(make_shot(), "", "hint").error


def test_estimate_cost():
    from types import SimpleNamespace

    u = SimpleNamespace(input_tokens=1_000_000, output_tokens=0)
    assert estimate_cost("claude-opus-5-5", u) == 4.0
    assert estimate_cost("unknown-model", SimpleNamespace(input_tokens=0, output_tokens=1_000_000)) == 20.0


def test_settings_roundtrip_and_bad_values(tmp_path):
    p = tmp_path / "c.json"
    s = Settings(mode="check", course_context="Birkbeck CS")
    s.save(p)
    assert Settings.load(p).course_context == "Birkbeck CS"
    p.write_text('{"mode": "nonsense", "effort": "ultra", "unknown_key": 1}')
    s2 = Settings.load(p)
    assert s2.mode == "breakdown" and s2.effort == "low"
    p.write_text('{"effort": "medium"}')  # a v0.2 config: old default upgraded to the faster one
    assert Settings.load(p).effort == "low"
    p.write_text('{"effort": "medium", "config_version": 2}')  # chosen on purpose: kept
    assert Settings.load(p).effort == "medium"
    p.write_text("{broken")
    assert Settings.load(p).mode == "breakdown"


def test_notes_markdown():
    import json

    exp = parse_explanation(json.dumps(SAMPLE), None)
    path = notes.save(exp, "stuck on q3", "breakdown", datetime(2026, 10, 8, 21, 5))
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# MoodleClicky notes - Thursday 08 October 2026")
    assert "## 21:05 - Q3" in text and "1. Look at the outer loop" in text and "**Answer:**" in text


def test_split_code():
    from moodleclicky.bubble import split_code

    parts = split_code("Answer:\n```python\nx = 1\n```\nDone")
    assert parts == [("Answer:", False), ("x = 1", True), ("Done", False)]


class FakeDeepSeek:
    def __init__(self, reply=None, finish="stop"):
        self.reply = json.dumps(SAMPLE) if reply is None else reply
        self.finish = finish
        self.payloads = []

    def chat(self, payload):
        self.payloads.append(json.loads(json.dumps(payload)))
        return {"choices": [{"message": {"content": self.reply, "reasoning_content": "hmm"},
                             "finish_reason": self.finish}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 1000}}


def test_deepseek_backend_wire_format():
    s = Settings(provider="deepseek", effort="medium")
    fake = FakeDeepSeek()
    t = Tutor(s, deepseek_client=fake)
    assert t.ready
    exp = t.ask(make_shot(), "help", "breakdown")
    assert not exp.error and exp.steps[0].point == (2320, 300)
    p = fake.payloads[0]
    assert p["model"] == "deepseek-flash" and p["response_format"] == {"type": "json_object"}
    assert p["reasoning_effort"] == "high"
    assert p["messages"][0]["role"] == "system" and "json" in p["messages"][0]["content"]
    user = p["messages"][1]["content"]
    assert user[0]["type"] == "image_url" and user[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert abs(exp.cost_usd - 0.0015) < 1e-9

    t.follow_up("and why?", "hint")
    roles = [m["role"] for m in fake.payloads[1]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert "reasoning_content" not in fake.payloads[1]["messages"][2]


def test_deepseek_errors_are_friendly():
    import io
    import urllib.error

    class Boom:
        def __init__(self, code):
            self.code = code

        def chat(self, payload):
            raise urllib.error.HTTPError("u", self.code, "x", {}, io.BytesIO(b"bad"))

    t = Tutor(Settings(provider="deepseek"), deepseek_client=Boom(401))
    exp = t.ask(make_shot(), "", "hint")
    assert "DeepSeek API key" in exp.error and t.history == []  # failed turn not kept
    assert "credit" in Tutor(Settings(provider="deepseek"), deepseek_client=Boom(402)).ask(
        make_shot(), "", "hint").error
    cut = Tutor(Settings(provider="deepseek"), deepseek_client=FakeDeepSeek(reply='{"title": "x"', finish="length"))
    assert "cut off" in cut.ask(make_shot(), "", "hint").error


def test_json_example_matches_schema_keys():
    from moodleclicky.brain import SCHEMA, json_example

    ex = json.loads(json_example(SCHEMA))
    assert set(ex) == set(SCHEMA["required"]) and set(ex["steps"][0]) == {"text", "label", "x", "y"}


def test_api_keys_per_provider(monkeypatch):
    from moodleclicky import config

    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-123")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.get_api_key("deepseek") == "ds-123"
    from moodleclicky.brain import has_key

    assert has_key(Settings(provider="deepseek"))


def test_apply_setup_from_installer(tmp_path):
    from moodleclicky.setup_cli import apply_setup

    stored, auto = {}, []
    s = Settings()
    lines = apply_setup({"provider": "deepseek", "api_key": " sk-test-1234 ", "your_name": "Dom",
                         "course_context": "Birkbeck CS", "start_with_windows": True, "record_mic": False,
                         "whisper_model": "base.en", "bogus": 1},
                        settings=s, store_key=lambda k, p: stored.update({p: k}) or True, autostart=auto.append)
    assert stored == {"deepseek": "sk-test-1234"} and auto == [True]
    assert s.provider == "deepseek" and s.your_name == "Dom" and not s.record_mic and s.whisper_model == "base.en"
    assert any("1234" in x for x in lines) and not any("sk-test" in x for x in lines)  # key never logged
    assert Settings.load().your_name == "Dom"  # persisted


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def tap(d, clock, hold=0.08, gap=0.1):
    d.watched_down()
    clock.t += hold
    d.watched_up()
    clock.t += gap


def test_double_tap_ctrl_rules():
    from moodleclicky.triggers import DoubleTap

    fired = []
    clock = Clock()
    d = DoubleTap(lambda: fired.append(clock.t), clock=clock)
    tap(d, clock)
    assert fired == []  # one tap: nothing
    tap(d, clock)
    assert len(fired) == 1  # clean double tap

    tap(d, clock, gap=1.0)  # too slow between taps
    tap(d, clock)
    assert len(fired) == 1
    tap(d, clock)  # ...but that second tap starts a fresh pair
    assert len(fired) == 2

    # Ctrl+C then Ctrl+V: Ctrl is used with other keys -> never a trigger
    for _ in range(2):
        d.watched_down()
        d.other_key()
        clock.t += 0.05
        d.watched_up()
    assert len(fired) == 2

    # holding Ctrl (e.g. Ctrl+scroll) doesn't count as a tap
    tap(d, clock, hold=0.8)
    tap(d, clock)
    assert len(fired) == 2

    clock.t += 5  # start the next scenario fresh

    # typing a letter between taps cancels
    tap(d, clock)
    d.other_key()
    tap(d, clock)
    assert len(fired) == 2

    clock.t += 5

    # auto-repeat key-down events while held are ignored
    d.watched_down()
    d.watched_down()
    clock.t += 0.05
    d.watched_up()
    tap(d, clock)
    assert len(fired) == 3

    # paused while we type into another app ourselves
    d.paused = True
    tap(d, clock)
    tap(d, clock)
    assert len(fired) == 3


def test_single_tap_mode():
    from moodleclicky.triggers import DoubleTap

    fired = []
    clock = Clock()
    d = DoubleTap(lambda: fired.append(1), taps=1, clock=clock)
    tap(d, clock)
    assert fired == [1]


def test_partial_fields_while_streaming():
    from moodleclicky.brain import partial_fields

    assert partial_fields('{"title": "Q3 \\"big\\" O", "summary": "How it gr') == {"title": 'Q3 "big" O'}
    full = '{"title": "A", "summary": "B", "type_text": "for i in range(n):\\n    x", "st'
    assert partial_fields(full) == {"title": "A", "summary": "B", "type_text": "for i in range(n):\n    x"}
    assert partial_fields("") == {}


def test_streaming_partials_and_type_text():
    from fakes import SAMPLE as S

    payload = dict(S, type_text="O(n^2)")
    fake = FakeClient(payload=payload)
    text = json.dumps(payload)
    fake.chunks = [text[i:i + 15] for i in range(0, len(text), 15)]
    seen = []
    exp = Tutor(Settings(), client=fake).ask(make_shot(), "", "breakdown", on_partial=seen.append)
    assert exp.type_text == "O(n^2)"
    assert seen and seen[0] == {"title": S["title"]}  # title arrives first, before the rest
    assert seen[-1]["type_text"] == "O(n^2)"
    assert len(seen) == len({json.dumps(x, sort_keys=True) for x in seen})  # only sent when something changed


def test_trigger_modes_watch_the_right_keys():
    from types import SimpleNamespace

    from moodleclicky.triggers import KeyTrigger

    kb = SimpleNamespace(Key=SimpleNamespace(ctrl="ctrl", ctrl_l="ctrl_l", ctrl_r="ctrl_r"))
    rc = KeyTrigger("double_rctrl", lambda: None)
    assert rc.tap.taps_needed == 2 and rc._is_watched("ctrl_r", kb)
    assert not rc._is_watched("ctrl_l", kb) and not rc._is_watched("ctrl", kb)  # PowerToys Find My Mouse key
    any_ctrl = KeyTrigger("double_ctrl", lambda: None)
    assert all(any_ctrl._is_watched(k, kb) for k in ("ctrl", "ctrl_l", "ctrl_r"))
    assert KeyTrigger("right_ctrl", lambda: None).tap.taps_needed == 1
    assert KeyTrigger("triple_ctrl", lambda: None).tap.taps_needed == 3
    assert Settings().trigger == "double_rctrl"


def test_triple_tap():
    from moodleclicky.triggers import DoubleTap

    fired = []
    clock = Clock()
    d = DoubleTap(lambda: fired.append(1), taps=3, clock=clock)
    tap(d, clock)
    tap(d, clock)
    assert fired == []  # two taps (PowerToys' shortcut) isn't enough
    tap(d, clock)
    assert fired == [1]


class SeqDeepSeek:
    """Returns the given replies in order (each a dict payload for the JSON content)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.payloads = []

    def chat(self, payload):
        self.payloads.append(json.loads(json.dumps(payload)))
        content = self.replies.pop(0)
        return {"choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10}}


BLIND = dict(SAMPLE, title="Unable to see question",
             summary="I can't see the screenshot - it appears as unsupported. Please describe what's at your cursor.")


def test_deepseek_retries_when_it_cant_see_the_screenshot():
    fake = SeqDeepSeek(BLIND, SAMPLE)
    exp = Tutor(Settings(provider="deepseek", deepseek_model="deepseek-v4-pro"), deepseek_client=fake).ask(
        make_shot(), "", "breakdown")
    assert not exp.error and exp.title == SAMPLE["title"]
    first, second = fake.payloads
    assert first["model"] == "deepseek-flash"  # v4-pro can't see images -> swapped for screenshots
    assert first["messages"][1]["content"][0]["type"] == "image_url"
    assert second["messages"][1]["content"][0]["type"] == "file"  # the other documented image format
    assert second["messages"][1]["content"][0]["file_data"].startswith("data:image/jpeg;base64,")
    assert second["thinking"] == {"type": "disabled"} and "reasoning_effort" not in second


def test_deepseek_still_blind_gives_clear_advice():
    exp = Tutor(Settings(provider="deepseek"), deepseek_client=SeqDeepSeek(BLIND, BLIND)).ask(
        make_shot(), "", "breakdown")
    assert "Switch to Claude" in exp.error


def test_looks_blind_only_on_real_failures():
    from moodleclicky.brain import looks_blind

    assert looks_blind(json.dumps(BLIND))
    assert not looks_blind(json.dumps(SAMPLE))
    normal = dict(SAMPLE, summary="The screenshot shows a SQL query; you need to describe what JOIN does.")
    assert not looks_blind(json.dumps(normal))


def test_claude_blind_reply_is_a_friendly_error():
    exp = Tutor(Settings(), client=FakeClient(payload=BLIND)).ask(make_shot(), "", "breakdown")
    assert "couldn't see your screen" in exp.error
