# MoodleClicky

**A study buddy that lives next to your mouse cursor.** Stuck on a Moodle question, a coursework task or an error in your code? Press a hotkey. MoodleClicky looks at your screen, flies over to the right spot, and walks you through it one small step at a time in a Clippy-style pop-up. No chatbot wall of text.

![MoodleClicky demo](docs/demo.gif)

> Personal Windows desktop app. Works with **Claude** or **DeepSeek**. Inspired by [Clicky](https://github.com/farzaa/clicky) for Mac, built for studying.
> Also has a **lecture and meeting notetaker** that records, transcribes on your PC, and catches you up if you zone out.

---

## Quick start (Windows)

**Option A: ready-made app (no Python needed)**

1. Open the **Actions** tab, then the latest green **CI** run, then download **MoodleClicky-windows**. Or grab it from **Releases**.
2. Unzip it anywhere (e.g. `Documents\MoodleClicky`).
3. Double-click **`MoodleClicky.exe`**.
4. Paste your API key in the settings window: a [Claude key](https://console.anthropic.com) or a [DeepSeek key](https://platform.deepseek.com).
5. Hover over a question and press **Ctrl + Alt + Space**.

**Option B: from source**

Install **Python 3.11+** from [python.org](https://www.python.org/downloads/) (tick *"Add python.exe to PATH"*). Download this repo, then double-click **`run.bat`**. The first run sets everything up.

The buddy then sits in your system tray. Click the tray icon to show or hide it. Turn on **Start with Windows** in Settings and it's always there.

## Hotkeys

| Keys | What it does |
|---|---|
| **Ctrl + Alt + Space** | "What are you stuck on?" Type a question, or just press Enter and it looks at what's under your cursor |
| **Ctrl + Alt + H** | Show or hide the cursor buddy |
| **Ctrl + Alt + N** | Open the lecture / meeting notetaker |
| **Ctrl + Alt + M** | ⭐ Mark "this bit matters" while recording (highlighted in your notes) |
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

## 🎙️ Lecture and meeting notetaker

For lectures (in person, Teams, Zoom or Panopto) and group-project meetings, especially when you can't give it 100% attention.

1. **Ctrl + Alt + N** (or tray → *Lecture / meeting notetaker*), pick **Lecture** or **Group meeting**, then press **Start**.
2. It records your **microphone and/or computer audio** and transcribes it **on your PC** (free, offline speech-to-text with Whisper). The live transcript scrolls as it goes.
3. Zoned out? Press **Catch me up** (2, 5 or 10 minutes). You get what's being discussed right now, what you missed, anything aimed at **you**, and something sensible to say if you're put on the spot.
4. Press **Make notes** at the end:
   - **Lecture**: summary, key points, concepts explained, examples, your ⭐ moments, to-dos and deadlines, "test yourself" questions.
   - **Group meeting**: decisions, who's doing what, **your tasks** (set your name in Settings), and a step-by-step plan.

| Live notetaker | Meeting notes it writes |
|---|---|
| ![Notetaker](docs/notetaker.png) | ![Meeting notes](docs/meeting_notes.png) |

**Built not to lose your notes:**
- The transcript is saved as it happens. If the laptop dies mid-lecture, reopen the session under **Past** and make notes from what was saved.
- If your mic gets unplugged, it keeps retrying.
- If no sound is playing, recording carries on regardless.
- Audio is deleted once it's transcribed.

Only record where you're allowed to, and tell your group first.

## Revision notes, for free

Every explanation is saved as Markdown, one file per day, in
`%APPDATA%\MoodleClicky\notes\`. Open the folder from the tray menu, then revise from it or paste it into OneNote or Obsidian.

## Cost and privacy

- You use **your own API key**. Each pop-up shows roughly what that answer cost and the running total for the session.
  - Claude Opus 5.5: about $0.01–0.03 per question.
  - DeepSeek Flash: a fraction of a cent.
- A screenshot is taken **only when you press the hotkey**. It's sent to the AI provider you picked and isn't stored anywhere else.
- Lecture audio never leaves your PC. Only the text transcript goes to the AI, and only when you press *Catch me up* or *Make notes*.
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
| `moodleclicky/lecture/` | Notetaker: `audio.py` (mic + loopback recorder), `transcribe.py` (Whisper), `session.py` (crash-safe sessions), `summarise.py` (notes, meeting plan, catch-up) |
| `moodleclicky/lecture_ui.py` | Notetaker window + notes viewer |
| `moodleclicky/theme.py` | Shared dark theme: pill buttons, segmented controls, toggles, cards |
| `moodleclicky/selftest.py` | `MoodleClicky.exe --selftest`: checks the build end to end, offline |

## Development

```bash
pip install -r requirements.txt pytest ruff bandit
pytest -q                                   # core tests (no API calls, fake client)
ruff check . && bandit -q -r moodleclicky   # lint + security scan
xvfb-run -a -s "-screen 0 1600x900x24" python tests/ui_smoke.py   # drives the real windows (Linux)
xvfb-run -a -s "-screen 0 1600x900x24" python tools/make_docs.py  # regenerates the screenshots + GIF
```

Build the Windows app yourself: `tools\build_exe.bat`. It runs PyInstaller, then self-tests the built `.exe`, and writes the output to `dist\MoodleClicky-windows.zip`. CI does the same on every push. Tag `v*` to publish a Release.

**Troubleshooting:** everything is logged to `%APPDATA%\MoodleClicky\moodleclicky.log`. Run `MoodleClicky.exe --selftest report.txt` to check an install.

## Use it fairly

This tool is built for **learning**: breakdowns, hints and checking your own work. Check your university's rules before using any AI help during assessed quizzes or exams.

MIT licence.
