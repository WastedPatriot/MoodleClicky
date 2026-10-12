<p align="center">
  <img src="docs/banner.png" alt="MoodleClicky: a study buddy that lives by your cursor" width="100%">
</p>

<p align="center">
  <a href="https://github.com/WastedPatriot/MoodleClicky/actions/workflows/ci.yml"><img alt="Build" src="https://github.com/WastedPatriot/MoodleClicky/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/WastedPatriot/MoodleClicky/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/WastedPatriot/MoodleClicky?label=release&color=4f8cff"></a>
  <img alt="Windows 10/11" src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?logo=windows&logoColor=white">
  <img alt="Linux X11" src="https://img.shields.io/badge/Linux-Parrot%20%7C%20Kali%20%7C%20Debian%20%7C%20Ubuntu-FCC624?logo=linux&logoColor=black">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white">
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-22c55e"></a>
</p>

Stuck on a Moodle quiz question, a coursework task or an error in your code? **Double-tap Ctrl.** MoodleClicky screenshots what's under your mouse, flies its little cursor buddy over to the part that matters, and talks you through it in a speech bubble, one step at a time. There's no chat window to open and nothing to type.

If you're writing in a text box, it also suggests what goes there. Double-tap again and it types it in for you. You can also just ask it something: **hold Ctrl and talk.** Still stuck? **Ctrl + Alt + A** moves your mouse onto the answer.

<p align="center"><img src="docs/demo.gif" alt="Demo: the cursor buddy explaining a Big-O question step by step" width="88%"></p>

It runs on **Windows and Linux**, and works with **Claude**, **DeepSeek** or **your own model** (Ollama, LM Studio, OpenRouter… free if it runs on your PC). It also comes with a **lecture and meeting notetaker** that transcribes on your PC and catches you up when you zone out.

---

## Install

### Windows

Open **PowerShell** (Start → type *PowerShell* → Enter) and paste:

```powershell
irm https://raw.githubusercontent.com/WastedPatriot/MoodleClicky/main/install.ps1 | iex
```

That one command:
1. Downloads the latest release (no Python or admin rights needed).
2. Adds Start menu and Desktop shortcuts.
3. Asks a few setup questions right in the terminal: Claude or DeepSeek, your API key (hidden as you type), your name and course, wake-up key, and speed.
4. Starts MoodleClicky in your system tray.

| | |
|---|---|
| **Update** | It checks for new versions by itself. When one is out, the buddy tells you. Tray icon → **Update now** (your settings, keys and notes are kept). |
| **Change settings** | Tray icon → **Settings**, or Start menu → **MoodleClicky Setup** |
| **Uninstall** | Start menu → **Uninstall MoodleClicky** (it asks whether to keep your notes) |
| **Offline install** | `.\install.ps1 -Zip path\to\MoodleClicky-windows.zip` |

### Linux (Parrot OS, Kali, Debian, Ubuntu, Mint…)

Open a terminal and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/WastedPatriot/MoodleClicky/main/install.sh | bash
```

It installs the few system packages it needs with `apt` (it asks first), puts everything in `~/.local/share/moodleclicky`, adds a menu entry, and runs the same setup questions. No root install, nothing system-wide besides those packages.

| | |
|---|---|
| **Update** | The buddy tells you, then tray → **Update now**. Or run `moodleclicky --update` |
| **Change settings** | Tray → **Settings**, or `moodleclicky --setup` |
| **Uninstall** | `moodleclicky --uninstall` |

It needs an **X11** session, which is the default on Parrot, Kali and Mint. On a Wayland desktop (stock Ubuntu/Fedora GNOME), pick *Xorg* on the login screen. Wayland doesn't let apps listen for global keys or take screenshots.

### Which AI?

| | Cost | Setup |
|---|---|---|
| **Claude** | ~1¢ per answer | API key from [console.anthropic.com](https://console.anthropic.com) |
| **DeepSeek** | a fraction of that | API key from [platform.deepseek.com](https://platform.deepseek.com) |
| **Your own model** | free if local | Any OpenAI-compatible server (see below) |

A Claude.ai / Claude Code subscription (Pro, Team, Enterprise) can't be used here. Apps need an API key, which is billed separately. For no per-answer cost at all, use a local model.

#### Using your own model

Pick **Custom** in Settings (or option 3 in the installer), then choose a preset or type the server address:

| Preset | Address | Notes |
|---|---|---|
| Ollama | `http://localhost:11434/v1` | `ollama pull qwen2.5vl:7b`. Free, private, works offline |
| LM Studio | `http://localhost:1234/v1` | Load a vision model, start the server |
| OpenRouter | `https://openrouter.ai/api/v1` | One key, hundreds of models |
| OpenAI / Groq / vLLM / llama.cpp | their `/v1` address | |

The model **must be able to see images**: `qwen2.5vl`, `gemma3`, `llama3.2-vision`, `llava` and similar all work. Smaller models point less precisely than Claude, but they're free. The API key is optional; local servers don't need one.

## Using it

1. Hover over the thing you're stuck on.
2. **Double-tap Ctrl** (either one). The buddy hops on the first tap, then grows, takes a look, and starts talking.
3. Read along. It points at each part as it explains, then fades away. Clicks go straight through it.

### Talking to it

- **Say it:** hold **Ctrl**, ask your question out loud ("why is this one quadratic?"), and let go. Your voice is turned into text on your PC and never uploaded. The buddy looks at your screen and answers in the bubble.
- **Type it:** press **Ctrl + Alt + Q**. A one-line box opens next to the buddy. Type, then press Enter.

| Keys | |
|---|---|
| **Ctrl ×2** | Look at what's under the mouse and explain it |
| **Copilot key** | Same, with one press (laptops that have one) |
| **Hold Ctrl** and talk | Ask a question out loud; let go when you're done |
| **Ctrl ×2** again (while it's talking) | Type the suggestion into the box you were in. Ctrl+Z undoes it |
| **Ctrl + Alt + A** | Move your mouse onto the answer (the right option, the box, the line). It never clicks |
| **Esc** | Hide the speech bubble |
| **Ctrl + Alt + Q** | Type a question in a small box by the buddy |
| **Ctrl + Alt + N** | Lecture / meeting notetaker |
| **Ctrl + Alt + M** | Mark "this bit matters" while recording |
| **Ctrl + Alt + H** | Show / hide the buddy |

Tapping Ctrl on its own does nothing in browsers, Word or IDEs, so it never gets in your way. Ctrl+C, Ctrl+V and Ctrl+click don't count as taps. If you use PowerToys' *Find My Mouse* (also Left Ctrl ×2), pick **Right Ctrl ×2** in Settings.

**Not responding?** Tap at a normal pace: two taps inside about half a second. Check the tray icon is there (it isn't running otherwise). The log at `%APPDATA%\MoodleClicky\moodleclicky.log` shows a `ctrl tap` line for every tap it hears.

### Modes

| | |
|---|---|
| **Breakdown** *(default)* | What the question is really asking → the steps → the answer → why it works |
| **Hint** | Nudges only, never the answer. Typing help just gives you a sentence starter. Ctrl + Alt + A shows *where* the answer is |
| **Check** | Write your answer first; it marks your working and points at what's wrong |

Want everything at once, with Back/Next and follow-up questions? Tray → **Show full answer**. If you prefer that card to the speech bubble every time, switch the bubble off in Settings.

| Speech bubble | Full answer |
|---|---|
| ![The buddy pointing at the inner loop](docs/pointing.png) | ![The full answer card](docs/answer.png) |
| **Hint mode** | **Typing a question** |
| ![Hint mode](docs/hint.png) | ![Ask a question](docs/prompt.png) |

## Lecture and meeting notetaker

For lectures (in the room, Teams, Zoom or Panopto) and group-project meetings.

- **Records** your microphone and/or the computer's own audio, and **transcribes it on your PC** with Whisper. Free, and the audio never leaves your machine.
- **Catch me up** (2, 5 or 10 min): what's being discussed now, what you missed, anything aimed at *you*, and something sensible to say if you're put on the spot.
- **Make notes**:
  - *Lectures*: key points, concepts explained, examples, deadlines, and test-yourself questions.
  - *Meetings*: decisions, who's doing what, **your** tasks, and a step-by-step plan.
- **Crash-safe:** the transcript is saved as it goes, so if the laptop dies you can make notes from the saved session later.

| Live transcript | Meeting notes it writes |
|---|---|
| ![Notetaker](docs/notetaker.png) | ![Meeting notes](docs/meeting_notes.png) |

Only record where you're allowed to, and tell your group first.

## Privacy and cost

- A screenshot is only taken when **you** trigger it. It goes to the AI provider you chose and nowhere else.
- Lecture audio stays on your PC. Only the text transcript is sent, and only when you ask for notes.
- API keys live in **Windows Credential Manager**, or the Linux keychain (Secret Service). If there's no keychain, they go in a `chmod 600` file only you can read.
- With a local model, nothing leaves your PC at all.
- You pay your provider directly. Each answer shows roughly what it cost.
  - With Claude on *Fast* that's usually around a cent.
  - DeepSeek is a fraction of that.
- Every explanation is also saved to `%APPDATA%\MoodleClicky\notes\` as Markdown, one file per day, so you can revise from it later.

## How it works

```
Ctrl ×2
  → hide our own windows, screenshot the monitor under the cursor (cursor ringed), JPEG
  → Claude / DeepSeek returns structured JSON:
      { title, summary, type_text, steps: [{ text, label, x, y }], answer, answer_x, answer_y, why, check_yourself }
  → title + summary stream into the speech bubble while the rest arrives
  → the buddy flies to each step's (x, y), mapped back from image to screen coordinates
  → Ctrl ×2 again: refocus your window, paste type_text, restore your clipboard
  → Ctrl + Alt + A: glide the real pointer to (answer_x, answer_y)
```

<details>
<summary>Code map</summary>

| | |
|---|---|
| `moodleclicky/app.py` | Wiring: tray, hotkeys, worker threads → Tk thread |
| `moodleclicky/triggers.py` | Double-tap detector (ignores Ctrl+C, held Ctrl, typing between taps) |
| `moodleclicky/brain.py` | Prompt + JSON schema, Claude / DeepSeek / OpenAI-compatible backends, streaming, cost |
| `moodleclicky/capture.py` | Multi-monitor screenshot, DPI-aware coordinate mapping |
| `moodleclicky/speech.py` | Speech bubble + the player that walks through the steps |
| `moodleclicky/buddy.py` | The cursor buddy (follows, flies to targets, grows when active) |
| `moodleclicky/typer.py` | Types a suggestion into the window you were in (Ctrl+Shift+V in Linux terminals) |
| `moodleclicky/x11shape.py` | Linux: see-through, click-through buddy and bubble (XShape) |
| `moodleclicky/winutil.py` | Platform glue: DPI, autostart (Run key / XDG), focus (Win32 / xdotool) |
| `moodleclicky/pointer.py` | Glides your mouse onto the answer |
| `moodleclicky/bubble.py` | Full answer card |
| `moodleclicky/lecture/` | Recorder (mic + WASAPI loopback), Whisper transcription, crash-safe sessions, notes |
| `moodleclicky/updater.py` | Checks GitHub Releases, updates in place |
| `moodleclicky/selftest.py` | `MoodleClicky.exe --selftest`: end-to-end check of an install |
| `install.ps1` / `install.sh` | Windows / Linux installer, setup menu, updater, uninstaller |

</details>

## How it's tested

Every push runs the same checks on Linux and on a real **Windows** machine ([CI workflow](.github/workflows/ci.yml)):

- **Unit tests** (`pytest`):
  - the double-tap rules (Ctrl+C, held keys, typing between taps)
  - screenshot ↔ screen coordinate maths across monitors
  - all three AI backends, against fakes, including streaming, retries and error messages. The custom backend is also tested against an Ollama-style server with no JSON mode that wraps its reply in `<think>` and code fences
  - the notetaker's recorder, crash recovery and note formats
  - real Whisper transcription of synthesised speech
- **UI test:** drives the real windows on a virtual screen:
  - double-tap → speech bubble → buddy points → typing with clipboard restore → Esc → full card → **Show me** glides the pointer onto the answer
  - settings scrolling on a laptop-sized screen
- **The built `.exe` tests itself** (`--selftest`) on Windows:
  - real key events at a relaxed human pace: either Ctrl ×2 wakes it, Ctrl+Shift doesn't, the Copilot key does, holding Ctrl is push-to-talk, and Right-Ctrl-only mode ignores Left Ctrl
  - a suggestion pasted into a real text box
  - the speech bubble, the notetaker, settings, and loading the speech model
- **Installer tests:**
  - **Windows:** `install.ps1` installs the fresh build with scripted answers, checks the shortcuts and saved settings, checks the app stays running, then uninstalls.
  - **Linux:** `install.sh` does the same on a clean Ubuntu machine (apt packages, venv, menu entry, custom-model setup), then runs the installed app's self-test with real X11 key events.
- **Lint and security scan:** `ruff` and `bandit`.

A release is only published if all of that passes.

## Development

```bash
pip install -r requirements.txt pytest ruff bandit
pytest -q
ruff check . && bandit -q -r moodleclicky
xvfb-run -a -s "-screen 0 1600x900x24" python tests/ui_smoke.py
python -m moodleclicky --selftest            # end-to-end, offline
xvfb-run -a -s "-screen 0 1600x900x24" python tools/make_docs.py   # regenerate screenshots + GIF
```

- **Windows build:** `tools\build_exe.bat`, which runs PyInstaller, self-tests the build and writes `dist\MoodleClicky-windows.zip`.
- **Logs:** `%APPDATA%\MoodleClicky\moodleclicky.log`
- **What changed between versions:** [CHANGELOG.md](CHANGELOG.md)

## Use it fairly

It's built for learning: breakdowns, hints and checking your own work. Check your university's rules before using any AI help on assessed quizzes or exams.

Inspired by [Clicky](https://github.com/farzaa/clicky) for macOS. MIT licence.
