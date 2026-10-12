# Changelog

All notable changes. Versions match the GitHub Releases that the installer downloads.

## [0.8.1] - 2026-10-12
### Changed
- **Type a question** is now **Ctrl + Alt + Q**. Ctrl + Alt + Space also opens the Claude desktop app's quick entry, so both popped up. Existing settings are moved over automatically; you can pick any key in Settings → Hotkeys.

## [0.8.0] - 2026-10-12
### Added
- **Linux** (Parrot OS, Kali, Debian, Ubuntu, Mint… on X11): one-line installer `install.sh` with the same setup menu, menu entry, start-at-login, self-update and uninstall.
  - The buddy and speech bubble are cut to shape with XShape, so they're see-through and click-through like on Windows.
  - Typing help knows terminals paste with Ctrl+Shift+V.
  - API keys go in the Secret Service keychain, or a private `chmod 600` file if there isn't one.
  - On Wayland it tells you to switch to an X11 session instead of silently ignoring your keys.
- **Custom / local AI:** any OpenAI-compatible server, such as Ollama, LM Studio, vLLM or llama.cpp on your own PC (free and private), or OpenRouter, OpenAI and Groq. There are presets in Settings and in both installers. Replies from smaller models are cleaned up (```json fences, `<think>` blocks, loose types).
- CI installs and self-tests on a fresh Ubuntu machine too, and a release now needs Linux and Windows to pass.

## [0.7.0] - 2026-10-12
### Changed
- **Waking it up is more forgiving.** The default is now double-tap **either** Ctrl, with relaxed timing, so an unhurried double-tap counts. If you were on the old Right-Ctrl-only default, you're moved over automatically. PowerToys *Find My Mouse* users can still pick "Right Ctrl ×2" in Settings.
- The buddy does a little hop on your first tap, so you can see it heard you.
- Ctrl+click (multi-select, open in a new tab) never counts as a tap or as hold-to-talk.
### Added
- **The Copilot key** wakes it with one press, on laptops that have one.
- **Show me the answer:** **Ctrl + Alt + A** (or **Show me** on the full card, or the tray) glides your real mouse pointer onto the answer: the right option, the box to fill in or the line to fix. It never clicks. In Hint mode this is the hint. You can also have it happen automatically in Settings.
- Wake-up key presses are written to the log, which helps when it doesn't respond.

## [0.6.0] - 2026-10-12
### Added
- **Talk to it:** hold Right Ctrl, ask out loud, let go. Speech is transcribed on your PC (Whisper `base.en`, preloaded in the background) and sent with a screenshot, and the answer appears in the speech bubble. You can turn it off in Settings.
- **Ctrl + Alt + Space** now opens a small one-line box next to the buddy instead of the big card.

## [0.5.0] - 2026-10-12
### Added
- **Auto-update.** The app checks GitHub once a day. When there's a new version, the buddy tells you, and tray → **Update now** installs it in place (settings, keys and notes are kept). You can turn this off in Settings.
- `install.ps1 -Update`: a quiet reinstall of the latest release, with no questions.
- Changelog, release notes and status badges.

## [0.4.0] - 2026-10-09
### Changed
- Answers now appear in a small **speech bubble** next to the cursor buddy instead of a big card. The text types itself out and walks through the summary → each step (the buddy points at the thing it's talking about) → answer → why, then fades.
- The bubble is click-through, so it never blocks what you're clicking. **Esc** hides it.
- The buddy grows while it's thinking or talking.
### Added
- Tray → **Show full answer** opens the full card (Back/Next, modes, follow-up questions).

## [0.3.2] - 2026-10-09
### Fixed
- DeepSeek sometimes replied that it "can't see the screenshot". Screenshots now always go to a model that can see images, and the app retries with DeepSeek's alternative image format. If it still fails, it says so plainly.

## [0.3.1] - 2026-10-09
### Changed
- Default wake-up key is now **double-tap Right Ctrl**. Double-tapping Left Ctrl is PowerToys' *Find My Mouse*, which also ended up in the screenshot.
### Added
- Wake-up key options: either Ctrl ×2, Ctrl ×3, Right Ctrl ×1, Ctrl+Alt+Space.
### Fixed
- The self-test could hang the Windows build. It now has a watchdog and live progress output.

## 0.3.0 - 2026-10-09
### Added
- **Double-tap to look:** no prompt and no Enter. Focus goes back to the box you were typing in.
- **Typing help:** when you're in a text box, it suggests what goes there. Trigger again to paste it at your caret (your clipboard is restored afterwards).
- Streaming replies: the title and summary show while the rest is still being written.
### Changed
- Faster: JPEG screenshots, shorter delays, and a "Fast" speed setting by default.

## [0.2.1] - 2026-10-09
### Added
- One-command install with a setup menu in the terminal, plus Start-menu shortcuts for Setup and Uninstall.
### Fixed
- Settings window: mouse-wheel scrolling, and the API key section is now first.

## 0.2.0 - 2026-10-09
### Added
- **Lecture / meeting notetaker:** records mic and/or computer audio, transcribes on your PC with Whisper, then "Catch me up" and "Make notes" (lecture notes, or a meeting plan with your tasks).
- Dark theme across every window.
- DeepSeek as an alternative to Claude.
- Single instance, crash log, start-with-Windows.
- Windows `.exe` build with a built-in self-test (`--selftest`).

## 0.1.0 - 2026-10-09
### Added
- First version: the cursor buddy and pop-up with Breakdown / Hint / Check modes, follow-up questions, tray icon, settings, and daily revision notes.

[0.8.1]: https://github.com/WastedPatriot/MoodleClicky/releases/tag/v0.8.1
