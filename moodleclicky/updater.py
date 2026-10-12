"""Checks GitHub for a newer release and updates in place (Windows installer, settings kept)."""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404 - launches our own installer script
import sys
import urllib.request

from moodleclicky import __version__

REPO = "WastedPatriot/MoodleClicky"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
INSTALL_SCRIPT = f"https://raw.githubusercontent.com/{REPO}/main/install.ps1"


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    return parse_version(latest) > parse_version(current)


def fetch_latest(timeout: float = 10.0) -> dict:
    req = urllib.request.Request(LATEST_API, headers={"User-Agent": f"MoodleClicky/{__version__}",
                                                      "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - fixed https URL
        return json.loads(resp.read().decode("utf-8"))


def check(fetch=fetch_latest) -> str | None:
    """Tag of a newer release (e.g. 'v0.5.0'), or None if up to date / offline."""
    try:
        tag = (fetch() or {}).get("tag_name", "")
    except Exception:  # offline, rate limited, repo private... never bother the user about it
        return None
    return tag if tag and is_newer(tag) else None


def can_self_update() -> bool:
    """Only the installed Windows app updates itself; from source you `git pull`."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def run_update() -> None:
    """Start the installer in update mode in its own window; it closes this app, swaps files, relaunches."""
    cmd = f"& ([scriptblock]::Create((irm '{INSTALL_SCRIPT}'))) -Update"
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],  # nosec B603 B607
                     creationflags=flags)
