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
PROVIDERS = ("anthropic", "deepseek", "custom")
PROVIDER_LABELS = {"anthropic": "Claude (Anthropic)", "deepseek": "DeepSeek",
                   "custom": "Custom / local (OpenAI-compatible)"}
DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "deepseek": "deepseek-flash", "custom": "qwen2.5vl:7b"}
# Any server that speaks the OpenAI /chat/completions API. The model must be able to see images.
CUSTOM_PRESETS = {
    "Ollama (this PC, free)": ("http://localhost:11434/v1", "qwen2.5vl:7b"),
    "LM Studio (this PC, free)": ("http://localhost:1234/v1", ""),
    "OpenRouter": ("https://openrouter.ai/api/v1", "google/gemini-2.5-flash"),
    "OpenAI": ("https://api.openai.com/v1", "gpt-4.1-mini"),
    "Groq": ("https://api.groq.com/openai/v1", "meta-llama/llama-4-scout-17b-16e-instruct"),
}


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
    custom_url: str = "http://localhost:11434/v1"  # OpenAI-compatible base URL (Ollama, LM Studio, OpenRouter…)
    custom_model: str = "qwen2.5vl:7b"  # must be able to see images
    effort: str = "low"  # low = fastest replies; medium/high think longer
    mode: str = "breakdown"
    trigger: str = "double_ctrl"  # double_ctrl | double_rctrl | triple_ctrl | right_ctrl | hotkey (triggers.py)
    instant: bool = True  # look straight away; False = ask "what are you stuck on?" first
    compact: bool = True  # Clicky-style speech bubble by the buddy; False = the full card
    hotkey_ask: str = "<ctrl>+<alt>+<space>"  # always opens the type-a-question prompt
    hotkey_toggle: str = "<ctrl>+<alt>+h"
    hotkey_show: str = "<ctrl>+<alt>+a"  # move your mouse onto the answer
    move_mouse_to_answer: bool = False  # do that automatically once it has explained
    buddy_visible: bool = True
    buddy_color: str = "#2f80ed"
    open_on_answer: bool = False  # False = walk through the steps first
    save_notes: bool = True
    check_updates: bool = True  # look for a newer release on GitHub once a day
    voice: bool = True  # hold Ctrl on its own and speak your question
    voice_model: str = "base.en"  # speech-to-text for push-to-talk (small + fast; runs on this PC)
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
    config_version: int = 3
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
        if raw.get("config_version", 1) < 3 and raw.get("trigger") == "double_rctrl":
            s.trigger = "double_ctrl"  # v0.6: Right-Ctrl-only confused people (many laptops have none)
        s.config_version = 3
        if s.mode not in MODES:
            s.mode = "breakdown"
        if s.effort not in EFFORTS:
            s.effort = "low"
        if s.trigger not in ("double_rctrl", "double_ctrl", "triple_ctrl", "right_ctrl", "hotkey"):
            s.trigger = "double_ctrl"
        if s.provider not in PROVIDERS:
            s.provider = "anthropic"
        if s.whisper_model not in WHISPER_MODELS:
            s.whisper_model = "small.en"
        return s

    def active_model(self) -> str:
        return {"deepseek": self.deepseek_model, "custom": self.custom_model}.get(self.provider, self.model)

    def save(self, path: Path | None = None) -> None:
        path = path or data_dir() / "config.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


# ---- API keys ------------------------------------------------------------
# Stored in Windows Credential Manager / macOS Keychain / Linux Secret Service via `keyring`, one per
# provider; if there is no keychain, in a chmod-600 keys.json in the data folder.
# ANTHROPIC_API_KEY / DEEPSEEK_API_KEY in the environment always win.

_KR_SERVICE = APP_NAME
_KR_USER = {"anthropic": "anthropic_api_key", "deepseek": "deepseek_api_key", "custom": "custom_api_key"}
_ENV = {"anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY", "custom": "MOODLECLICKY_CUSTOM_API_KEY"}


def _key_file() -> Path:
    return data_dir() / "keys.json"


def _file_keys() -> dict:
    try:
        return json.loads(_key_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_file_keys(keys: dict) -> bool:
    """Fallback when there's no OS keychain (e.g. a Linux desktop without gnome-keyring): a file only
    you can read (chmod 600)."""
    path = _key_file()
    try:
        if not keys:
            path.unlink(missing_ok=True)
            return True
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(keys, f)
        os.chmod(path, 0o600)
        return True
    except OSError:
        return False


def _keyring():
    """The OS keychain, or None if there isn't a usable one."""
    try:
        import keyring
        from keyring.backends import fail

        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
        return keyring
    except Exception:  # no backend available / broken D-Bus
        return None


def get_api_key(provider: str = "anthropic") -> str:
    env = os.environ.get(_ENV[provider], "").strip()
    if env:
        return env
    kr = _keyring()
    if kr is not None:
        try:
            got = (kr.get_password(_KR_SERVICE, _KR_USER[provider]) or "").strip()
            if got:
                return got
        except Exception:  # nosec B110 - locked/broken keychain: try the fallback file
            pass
    return str(_file_keys().get(provider, "")).strip()


def set_api_key(key: str, provider: str = "anthropic") -> bool:
    key = key.strip()
    kr = _keyring()
    if kr is not None:
        try:
            if key:
                kr.set_password(_KR_SERVICE, _KR_USER[provider], key)
            else:
                try:
                    kr.delete_password(_KR_SERVICE, _KR_USER[provider])
                except Exception:  # nosec B110 - nothing stored yet
                    pass
            keys = _file_keys()
            if keys.pop(provider, None) is not None:
                _write_file_keys(keys)
            return True
        except Exception:  # nosec B110 - keychain refused: use the fallback file
            pass
    keys = _file_keys()
    if key:
        keys[provider] = key
    else:
        keys.pop(provider, None)
    return _write_file_keys(keys)
