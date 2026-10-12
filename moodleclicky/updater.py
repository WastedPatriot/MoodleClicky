"""Checks GitHub for a newer release and updates in place (install.ps1 / install.sh, settings kept)."""

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
INSTALL_SH = f"https://raw.githubusercontent.com/{REPO}/main/install.sh"


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


def installed_by_script() -> bool:
    """Linux: running from the venv that install.sh made (~/.local/share/moodleclicky/venv)."""
    from pathlib import Path

    return Path(sys.prefix).name == "venv" and Path(sys.prefix).parent.name == "moodleclicky"


def can_self_update() -> bool:
    """The installed app updates itself; from a git checkout you `git pull`."""
    if sys.platform.startswith("linux"):
        return installed_by_script()
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def run_update() -> None:
    """Start the installer in update mode; it closes this app, swaps files, relaunches."""
    if sys.platform.startswith("linux"):
        from moodleclicky.config import data_dir

        log = open(data_dir() / "update.log", "w")  # noqa: SIM115 - handed to the child process
        subprocess.Popen(["bash", "-c", f'curl -fsSL "{INSTALL_SH}" | bash -s -- --update'],  # nosec B603 B607
                         stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
        return
    cmd = f"& ([scriptblock]::Create((irm '{INSTALL_SCRIPT}'))) -Update"
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],  # nosec B603 B607
                     creationflags=flags)
