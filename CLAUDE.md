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
- `brain.py` backends: ClaudeBackend (anthropic SDK) + DeepSeekBackend (stdlib HTTP, deepseek-flash vision + JSON
  mode); history is provider-neutral dicts
- `lecture/` notetaker: audio.py (soundcard mic+loopback, wall-clock mixer, 30 s WAV chunks), transcribe.py
  (faster-whisper, we decode WAV ourselves - no PyAV), session.py (crash-safe session.json/transcript.md),
  summarise.py (lecture/meeting/catch-up schemas); `lecture_ui.py` panel; `theme.py` shared dark widgets
- `selftest.py`: `python -m moodleclicky --selftest [report] [--with-model]` - offline end-to-end check (CI runs it
  against the built exe)
- `tools/make_docs.py` regenerates docs/*.png + demo.gif under xvfb (no API calls)
- `tools/build_windows.ps1` PyInstaller onedir build + exe self-test + zip (CI windows job, tags -> Release)

## Rules
- Commit author: WastedPatriot <106580482+WastedPatriot@users.noreply.github.com> (owner's GitHub noreply). Lint: `ruff check .`, `bandit -r moodleclicky`.
- Tests: `pytest -q` and `xvfb-run -a -s "-screen 0 1600x900x24" python tests/ui_smoke.py`. Keep green.
- Tests never call the real API — use `tests/fakes.py` FakeClient.
- Default model `claude-opus-5-5`, adaptive thinking, effort from settings, server-side fallbacks on.

## Ideas / next up
1. Push-to-talk voice question (hold hotkey, speak) - reuse lecture/transcribe.py.
2. "Explain like I'm tired" brevity slider; per-module course context presets.
3. Notetaker: grab slide screenshots at ⭐ marks and attach them to notes.
