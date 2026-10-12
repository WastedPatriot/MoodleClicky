"""Print the CHANGELOG section for a version + install instructions (used as the GitHub Release body)."""

import re
import sys
from pathlib import Path

INSTALL = """
### Install or update

Paste into PowerShell (no admin needed, keeps your settings):

```powershell
irm https://raw.githubusercontent.com/WastedPatriot/MoodleClicky/main/install.ps1 | iex
```

Already installed? Tray icon -> **Update now**.
"""


def section(changelog: str, version: str) -> str:
    m = re.search(rf"^## \[?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^## |\Z)", changelog, re.S | re.M)
    return m.group(1).strip() if m else ""


if __name__ == "__main__":
    version = sys.argv[1].lstrip("v")
    text = Path(__file__).resolve().parents[1].joinpath("CHANGELOG.md").read_text(encoding="utf-8")
    print((section(text, version) or "Bug fixes and improvements.") + "\n" + INSTALL)
