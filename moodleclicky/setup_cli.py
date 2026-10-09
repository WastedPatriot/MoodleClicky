"""`MoodleClicky.exe --apply-setup`: save the answers from the install menu (install.ps1), no window.

The installer passes everything through the MOODLECLICKY_SETUP environment variable (JSON), so the API key
never appears on a command line. Exit code 0 = saved. A short report goes to %APPDATA%\\MoodleClicky\\setup.log.
"""

from __future__ import annotations

import json
import os

from moodleclicky.config import PROVIDERS, WHISPER_MODELS, Settings, data_dir, set_api_key

ENV = "MOODLECLICKY_SETUP"
BOOL_FIELDS = ("start_with_windows", "record_mic", "record_system", "buddy_visible")
TEXT_FIELDS = ("your_name", "course_context")


def apply_setup(payload: dict, settings: Settings | None = None, store_key=set_api_key, autostart=None) -> list[str]:
    """Merge installer answers into the saved settings. Returns human-readable lines of what changed."""
    s = settings or Settings.load()
    done = []
    provider = payload.get("provider")
    if provider in PROVIDERS:
        s.provider = provider
        done.append(f"provider = {provider}")
    key = (payload.get("api_key") or "").strip()
    if key:
        if not store_key(key, s.provider):
            raise RuntimeError("Couldn't save the API key to Windows Credential Manager")
        done.append(f"{s.provider} API key saved (…{key[-4:]})")
    for f in TEXT_FIELDS:
        if f in payload:
            setattr(s, f, str(payload[f]).strip())
            done.append(f"{f} = {getattr(s, f)!r}")
    for f in BOOL_FIELDS:
        if f in payload:
            setattr(s, f, bool(payload[f]))
            done.append(f"{f} = {getattr(s, f)}")
    if payload.get("whisper_model") in WHISPER_MODELS:
        s.whisper_model = payload["whisper_model"]
        done.append(f"whisper_model = {s.whisper_model}")
    s.save()
    if autostart is None:
        from moodleclicky.winutil import set_autostart as autostart
    autostart(s.start_with_windows)  # also re-points the Run key at this (new) install
    return done


def main() -> int:
    log = data_dir() / "setup.log"
    try:
        payload = json.loads(os.environ.get(ENV) or "{}")
        lines = apply_setup(payload)
        log.write_text("OK\n" + "\n".join(lines) + "\n", encoding="utf-8")
        return 0
    except Exception as e:  # report to the installer via exit code + log
        log.write_text(f"FAILED: {type(e).__name__}: {e}\n", encoding="utf-8")
        return 1
