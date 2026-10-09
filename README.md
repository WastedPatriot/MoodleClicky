# MoodleClicky

**A study buddy that lives next to your mouse cursor.** Stuck on a Moodle question, a coursework task or an error in your code? Press a hotkey. MoodleClicky looks at your screen, flies over to the right spot, and walks you through it one small step at a time in a Clippy-style pop-up. No chatbot wall of text.

![MoodleClicky demo](docs/demo.gif)

> Personal Windows desktop app. Works with **Claude** or **DeepSeek**. Inspired by [Clicky](https://github.com/farzaa/clicky) for Mac, built for studying.

---

## Quick start (Windows)

1. Install **Python 3.11+** from [python.org](https://www.python.org/downloads/) and tick *"Add python.exe to PATH"*.
2. Download this repo (**Code → Download ZIP**) and unzip it.
3. Double-click **`run.bat`**. The first run sets everything up, which takes about a minute.
4. In the settings window, paste your API key: either a [Claude key](https://console.anthropic.com) or a [DeepSeek key](https://platform.deepseek.com).
5. Hover over a question and press **Ctrl + Alt + Space**.

The buddy then sits in your system tray. Click the tray icon to show or hide it.

## Hotkeys

| Keys | What it does |
|---|---|
| **Ctrl + Alt + Space** | "What are you stuck on?" Type a question, or just press Enter and it looks at what's under your cursor |
| **Ctrl + Alt + H** | Show or hide the cursor buddy |
| **← / →** | Previous / next step in the pop-up |
| **Esc** | Close the pop-up |

You can change all of these in Settings (⚙ in the pop-up, or right-click the tray icon).

## Three modes

| Mode | What you get |
|---|---|
| **Breakdown** (default) | What the question is really asking, then the steps one at a time, with the buddy pointing at each part, then the answer, why it works, and a quick "check yourself" question |
| **Hint** | Nudges only, no answer. For when you want to get there yourself |
| **Check** | Write your answer first, then it marks your working and points at what's off |

Switch modes in the pop-up at any time. You can also type follow-up questions ("why n squared?") in the box at the bottom.

## Screenshots

| Pointing at the code | The answer, with a breakdown |
|---|---|
| ![Pointing](docs/pointing.png) | ![Answer](docs/answer.png) |
| **Hint mode: no spoilers** | **Ask anything** |
| ![Hint](docs/hint.png) | ![Prompt](docs/prompt.png) |

<img src="docs/settings.png" alt="Settings" width="480">

## Revision notes, for free

Every explanation is saved as Markdown, one file per day, in
`%APPDATA%\MoodleClicky\notes\`. Open the folder from the tray menu, then revise from it or paste it into OneNote or Obsidian.

## Cost and privacy

- You use **your own API key**. Each pop-up shows roughly what that answer cost and the running total for the session.
  - Claude Opus 5.5: about $0.01–0.03 per question.
  - DeepSeek Flash: a fraction of a cent.
- A screenshot is taken **only when you press the hotkey**. It's sent to the AI provider you picked and isn't stored anywhere else.
- Your API keys are stored in **Windows Credential Manager**, not in a text file.

## How it works

```
hotkey ─► hide own windows ─► screenshot the monitor under the cursor (cursor ringed)
       ─► Claude / DeepSeek returns JSON: title, summary, steps[{text, x, y}], answer, why, check_yourself
       ─► buddy flies to each step's (x, y) ─► pop-up pages through the steps
```

| File | Job |
|---|---|
| `moodleclicky/app.py` | Wiring: hotkeys (pynput), tray icon (pystray), worker threads |
| `moodleclicky/brain.py` | Prompt, JSON schema, Claude and DeepSeek backends, cost estimate |
| `moodleclicky/capture.py` | Screenshot of the right monitor; maps the AI's coordinates back to the screen |
| `moodleclicky/buddy.py` | The cursor buddy (follows you, flies to targets, thinking dots) |
| `moodleclicky/bubble.py` | The pop-up (pages, back/next, show answer, follow-ups) |
| `moodleclicky/settings_ui.py` / `config.py` | Settings window, and settings stored in `%APPDATA%\MoodleClicky` |
| `moodleclicky/notes.py` | Daily revision notes |

## Development

```bash
pip install -r requirements.txt pytest ruff bandit
pytest -q                                   # core tests (no API calls, fake client)
ruff check . && bandit -q -r moodleclicky   # lint + security scan
xvfb-run -a -s "-screen 0 1600x900x24" python tests/ui_smoke.py   # drives the real windows (Linux)
xvfb-run -a -s "-screen 0 1600x900x24" python tools/make_docs.py  # regenerates the screenshots + GIF
```

Optional single `.exe`: `tools\build_exe.bat` (PyInstaller, output in `dist\`).

## Use it fairly

This tool is built for **learning**: breakdowns, hints and checking your own work. Check your university's rules before using any AI help during assessed quizzes or exams.

MIT licence.
