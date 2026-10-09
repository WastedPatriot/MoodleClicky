# MoodleClicky — notes for Claude Code

Personal Windows desktop study buddy (Python 3.11+, Tkinter). Owner: WastedPatriot. MIT. Private repo, personal use.
User prefers short, ADHD-friendly answers: next action first, numbered steps, ≤5 items.

## How it works
Hotkey → hide own windows → screenshot monitor under cursor (cursor ringed) → Claude (structured JSON: title,
summary, steps[{text,label,x,y}], answer, why, check_yourself) → cursor buddy flies to each step's (x,y) while
the Clippy-style bubble pages through summary → steps → answer → why → check-yourself.

## Layout
- `moodleclicky/app.py` wiring: hotkeys (pynput), tray (pystray), worker threads → `call_soon` queue → Tk thread
- `brain.py` Tutor (Claude call, SYSTEM prompt, SCHEMA, append-only history, cost estimate)
- `capture.py` mss screenshot + scaling; `Shot.to_screen` maps Claude's image coords back to screen coords
- `buddy.py` the arrow sprite (x/y = tip position); `bubble.py` the pop-up (pages, nav, follow-ups)
- `settings_ui.py`, `config.py` (JSON in %APPDATA%\MoodleClicky, API key in Windows Credential Manager)
- `notes.py` daily Markdown revision notes; `winutil.py` DPI awareness + click-through (Windows only)
- `tools/make_docs.py` regenerates docs/*.png + demo.gif under xvfb (no API calls)

## Rules
- Commit author: Claude <noreply@anthropic.com>. Lint: `ruff check .`, `bandit -r moodleclicky`.
- Tests: `pytest -q` and `xvfb-run -a -s "-screen 0 1600x900x24" python tests/ui_smoke.py`. Keep green.
- Tests never call the real API — use `tests/fakes.py` FakeClient.
- Default model `claude-opus-5-5`, adaptive thinking, effort from settings, server-side fallbacks on.

## Ideas / next up
1. Push-to-talk voice question (hold hotkey, speak).
2. "Explain like I'm tired" brevity slider; per-module course context presets.
3. Start-with-Windows toggle in settings.
