"""Settings: a small JSON file in the user's app-data folder, API key in the OS keychain."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from moodleclicky import APP_NAME

MODES = ("breakdown", "hint", "check")
MODE_LABELS = {
    "breakdown": "Breakdown — answer + step-by-step why",
    "hint": "Hint — nudge me, no answer",
    "check": "Check — mark my working",
}
EFFORTS = ("low", "medium", "high")
WHISPER_MODELS = ("tiny.en", "base.en", "small.en", "medium.en")
PROVIDERS = ("anthropic", "deepseek")
PROVIDER_LABELS = {"anthropic": "Claude (Anthropic)", "deepseek": "DeepSeek"}
DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "deepseek": "deepseek-flash"}


def data_dir() -> Path:
    override = os.environ.get("MOODLECLICKY_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME.lower()
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class Settings:
    provider: str = "anthropic"  # anthropic | deepseek
    model: str = "claude-opus-5-5"  # Claude model
    deepseek_model: str = "deepseek-flash"  # must be a vision-capable DeepSeek model
    effort: str = "low"  # low = fastest replies; medium/high think longer
    mode: str = "breakdown"
    trigger: str = "double_ctrl"  # double_ctrl | right_ctrl | hotkey  (see triggers.py)
    instant: bool = True  # look straight away; False = ask "what are you stuck on?" first
    hotkey_ask: str = "<ctrl>+<alt>+<space>"  # always opens the type-a-question prompt
    hotkey_toggle: str = "<ctrl>+<alt>+h"
    buddy_visible: bool = True
    buddy_color: str = "#2f80ed"
    open_on_answer: bool = False  # False = walk through the steps first
    save_notes: bool = True
    course_context: str = ""  # e.g. "Birkbeck BSc Computer Science, Year 2"
    max_image_edge: int = 1568
    # Lecture / meeting notetaker (see moodleclicky/lecture)
    hotkey_notes: str = "<ctrl>+<alt>+n"  # open the notetaker panel
    hotkey_mark: str = "<ctrl>+<alt>+m"  # flag "this bit matters" while recording
    record_mic: bool = True
    record_system: bool = True  # computer audio (Teams/Zoom/Panopto)
    whisper_model: str = "small.en"  # local speech-to-text: tiny.en | base.en | small.en | medium.en
    your_name: str = ""  # so group-meeting notes can pull out YOUR tasks
    start_with_windows: bool = False
    config_version: int = 2
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        path = path or data_dir() / "config.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        s = cls(**{k: v for k, v in raw.items() if k in known})
        if raw.get("config_version", 1) < 2:  # v0.2 saved "medium" by default; v0.3 defaults to fast replies
            if raw.get("effort", "medium") == "medium":
                s.effort = "low"
            s.config_version = 2
        if s.mode not in MODES:
            s.mode = "breakdown"
        if s.effort not in EFFORTS:
            s.effort = "low"
        if s.trigger not in ("double_ctrl", "right_ctrl", "hotkey"):
            s.trigger = "double_ctrl"
        if s.provider not in PROVIDERS:
            s.provider = "anthropic"
        if s.whisper_model not in WHISPER_MODELS:
            s.whisper_model = "small.en"
        return s

    def active_model(self) -> str:
        return self.deepseek_model if self.provider == "deepseek" else self.model

    def save(self, path: Path | None = None) -> None:
        path = path or data_dir() / "config.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


# ---- API keys ------------------------------------------------------------
# Stored in Windows Credential Manager / macOS Keychain via `keyring`, one per provider.
# ANTHROPIC_API_KEY / DEEPSEEK_API_KEY in the environment always win.

_KR_SERVICE = APP_NAME
_KR_USER = {"anthropic": "anthropic_api_key", "deepseek": "deepseek_api_key"}
_ENV = {"anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}


def get_api_key(provider: str = "anthropic") -> str:
    env = os.environ.get(_ENV[provider], "").strip()
    if env:
        return env
    try:
        import keyring

        return (keyring.get_password(_KR_SERVICE, _KR_USER[provider]) or "").strip()
    except Exception:  # no backend available
        return ""


def set_api_key(key: str, provider: str = "anthropic") -> bool:
    try:
        import keyring

        if key:
            keyring.set_password(_KR_SERVICE, _KR_USER[provider], key.strip())
        else:
            try:
                keyring.delete_password(_KR_SERVICE, _KR_USER[provider])
            except Exception:  # nosec B110 - nothing stored yet
                pass
        return True
    except Exception:
        return False
