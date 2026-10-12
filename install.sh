#!/usr/bin/env bash
# MoodleClicky for Linux (Parrot OS, Kali, Debian, Ubuntu, Mint… on an X11 desktop).
#
#   curl -fsSL https://raw.githubusercontent.com/WastedPatriot/MoodleClicky/main/install.sh | bash
#
# Options:  --setup      just re-run the setup questions
#           --update     reinstall the latest version, keep settings, relaunch (used by the app's updater)
#           --uninstall  remove it (asks whether to keep your notes)
#           --from DIR   install from a local checkout instead of downloading
#           --yes        don't ask before installing system packages with apt
set -euo pipefail

REPO="WastedPatriot/MoodleClicky"
HOME_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/moodleclicky"
APP="$HOME_DIR/app"
VENV="$HOME_DIR/venv"
BIN="$HOME/.local/bin/moodleclicky"
DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications/moodleclicky.desktop"
ICON="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps/moodleclicky.png"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/moodleclicky.desktop"
DATA="${MOODLECLICKY_HOME:-${XDG_CONFIG_HOME:-$HOME/.config}/moodleclicky}"

MODE=install; FROM=""; YES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --setup) MODE=setup ;;
    --update) MODE=update ;;
    --uninstall) MODE=uninstall ;;
    --from) FROM="$2"; shift ;;
    --yes|-y) YES=1 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# Piped from curl, stdin is this script: read answers from the terminal instead (if there is one).
# Answers are read from fd 3, opened once (reopening /dev/stdin would rewind a piped-in answers file).
TTY=0
if [ ! -t 0 ] && [ -z "${MC_STDIN:-}" ] && (: </dev/tty) 2>/dev/null; then exec 3</dev/tty; TTY=1
else exec 3<&0; [ -t 0 ] && TTY=1; fi

c() { printf '\033[%sm%s\033[0m' "$1" "$2"; }
say() { printf '  %s\n' "$*"; }
step() { printf '\n%s %s\n' "$(c '1;34' '==>')" "$(c 1 "$*")"; }
die() { printf '\n  %s %s\n\n' "$(c '1;31' 'Problem:')" "$*" >&2; exit 1; }

ask() {  # ask "Question" "default" -> REPLY
  local q="$1" d="${2:-}" a
  if [ -n "$d" ]; then printf '  %s [%s]: ' "$q" "$d"; else printf '  %s: ' "$q"; fi
  IFS= read -r a <&3 || a=""
  REPLY="${a:-$d}"
}
ask_secret() {
  local a
  printf '  %s: ' "$1"
  if [ "$TTY" = 1 ]; then IFS= read -rs a <&3 || a=""; echo; else IFS= read -r a <&3 || a=""; fi
  REPLY="$a"
}
ask_yes() {  # ask_yes "Question" y|n -> 0 = yes
  local d="$2" a
  printf '  %s [%s]: ' "$1" "$([ "$d" = y ] && echo Y/n || echo y/N)"
  IFS= read -r a <&3 || a=""
  a="${a:-$d}"
  case "$a" in [Yy]*) return 0 ;; *) return 1 ;; esac
}
choose() {  # choose "Question" default_index option... -> REPLY = 1-based index
  local q="$1" d="$2" i=1; shift 2
  say "$q"
  for o in "$@"; do say "  $(c 36 "$i)") $o"; i=$((i + 1)); done
  while :; do
    ask "Pick 1-$#" "$d"
    case "$REPLY" in ''|*[!0-9]*) ;; *) if [ "$REPLY" -ge 1 ] && [ "$REPLY" -le $# ]; then return; fi ;; esac
    say "$(c 33 'Type a number from the list.')"
  done
}

banner() {
  printf '\n'
  say "$(c '1;34' '  ▲')  $(c 1 'MoodleClicky')  $(c 2 'a study buddy that lives by your cursor')"
  say "$(c 2 '  Linux installer')"
}

stop_app() { pkill -f "$VENV/bin/python.* -m moodleclicky" 2>/dev/null || true; sleep 1; }

need_packages() {
  local missing=()
  command -v python3 >/dev/null || missing+=(python3)
  python3 -c 'import venv, ensurepip' 2>/dev/null || missing+=(python3-venv)
  python3 -c 'import tkinter' 2>/dev/null || missing+=(python3-tk)
  command -v xdotool >/dev/null || missing+=(xdotool)
  command -v xprop >/dev/null || missing+=(x11-utils)
  python3 -c 'import gi' 2>/dev/null || missing+=(python3-gi)
  if command -v dpkg >/dev/null; then
    dpkg -s gir1.2-ayatanaappindicator3-0.1 >/dev/null 2>&1 || missing+=(gir1.2-ayatanaappindicator3-0.1)
    dpkg -s libportaudio2 >/dev/null 2>&1 || missing+=(libportaudio2)
  fi
  printf '%s\n' "${missing[@]}"
}

install_packages() {
  step "Checking system packages"
  mapfile -t missing < <(need_packages)
  if [ ${#missing[@]} -eq 0 ]; then say "All there."; return; fi
  say "Needs: $(c 1 "${missing[*]}")"
  if ! command -v apt-get >/dev/null; then
    say "$(c 33 'Not a Debian-based system - install those with your package manager, then run this again.')"
    return
  fi
  if [ "$YES" = 1 ] || ask_yes "Install them now with sudo apt?" y; then
    local sudo=sudo; [ "$(id -u)" = 0 ] && sudo=""
    { $sudo apt-get update -qq && DEBIAN_FRONTEND=noninteractive $sudo apt-get install -y -qq "${missing[@]}"; } \
      >/dev/null || die "apt couldn't install: ${missing[*]}"
    say "Installed."
  else
    say "$(c 33 'Skipped - some features (tray icon, typing help) may not work.')"
  fi
}

PY=""
pick_python() {  # the first Python 3.11+ that has Tk and venv
  local cand
  for cand in python3 python3.13 python3.12 python3.11; do
    command -v "$cand" >/dev/null || continue
    if "$cand" -c 'import sys, tkinter, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PY="$(command -v "$cand")"; return 0
    fi
  done
  return 1
}

fetch_source() {
  step "Getting MoodleClicky"
  local tmp; tmp="$(mktemp -d)"
  if [ -n "$FROM" ]; then
    [ -f "$FROM/moodleclicky/__init__.py" ] || die "--from $FROM isn't a MoodleClicky folder"
    cp -r "$FROM" "$tmp/src"
    say "From $FROM"
  else
    local tag url
    tag="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
           | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tag_name",""))' 2>/dev/null || true)"
    if [ -n "$tag" ]; then url="https://github.com/$REPO/archive/refs/tags/$tag.tar.gz"; else url="https://github.com/$REPO/archive/refs/heads/main.tar.gz"; fi
    say "Downloading ${tag:-latest main}…"
    curl -fsSL "$url" -o "$tmp/src.tar.gz" || die "Download failed - check your internet connection."
    mkdir "$tmp/src" && tar -xzf "$tmp/src.tar.gz" -C "$tmp/src" --strip-components=1
  fi
  rm -rf "$APP"
  mkdir -p "$HOME_DIR"
  mv "$tmp/src" "$APP"
  rm -rf "$tmp"
}

make_venv() {
  step "Installing Python packages (first time takes a few minutes)"
  if [ ! -x "$VENV/bin/python" ]; then
    "$PY" -m venv --system-site-packages "$VENV" || die "Couldn't create a Python environment (is python3-venv installed?)"
  fi
  "$VENV/bin/python" -m pip install -q --upgrade pip
  "$VENV/bin/python" -m pip install -q -r "$APP/requirements.txt" || die "pip install failed (see above)."
  # Make `python -m moodleclicky` work from anywhere (launcher, autostart entry) without packaging it.
  "$VENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])' | {
    read -r site; printf '%s\n' "$APP" >"$site/moodleclicky-app.pth"; }
  say "Done."
}

make_shortcuts() {
  step "Adding launcher and menu entry"
  mkdir -p "$(dirname "$BIN")" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
  cat >"$BIN" <<EOF
#!/usr/bin/env bash
# MoodleClicky launcher (installed by install.sh)
case "\${1:-}" in
  --setup|--update|--uninstall) exec bash "$APP/install.sh" "\$@" ;;
  --selftest|--apply-setup) exec "$VENV/bin/python" -m moodleclicky "\$@" ;;
esac
nohup "$VENV/bin/python" -m moodleclicky "\$@" >/dev/null 2>&1 &
EOF
  chmod +x "$BIN"
  "$VENV/bin/python" -c "
from moodleclicky.app import tray_image
tray_image('#2f80ed').resize((256, 256)).save('$ICON')" 2>/dev/null || true
  cat >"$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=MoodleClicky
Comment=Study buddy that lives by your cursor
Exec=$BIN
Icon=$ICON
Terminal=false
Categories=Education;Utility;
EOF
  case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) say "$(c 33 "Tip: add ~/.local/bin to your PATH to run 'moodleclicky' from a terminal.")" ;; esac
  say "Menu → Education → MoodleClicky, or run: moodleclicky"
}

current() {  # current KEY -> value from the saved config (empty if none)
  [ -f "$DATA/config.json" ] || return 0
  python3 -c "import json,sys; v=json.load(open(sys.argv[1])).get(sys.argv[2],''); print(str(v).lower() if isinstance(v,bool) else v)" "$DATA/config.json" "$1" 2>/dev/null || true
}

setup_menu() {
  step "Setup (Enter = keep the [default])"
  local providers=(anthropic deepseek custom) p_idx=1 provider key url="" model=""
  case "$(current provider)" in deepseek) p_idx=2 ;; custom) p_idx=3 ;; esac
  choose "Which AI should it use?" "$p_idx" \
    "Claude (Anthropic) - best explanations" \
    "DeepSeek - cheaper" \
    "Custom / local - Ollama, LM Studio, OpenRouter… (any OpenAI-compatible server; free if local)"
  provider="${providers[$((REPLY - 1))]}"
  if [ "$provider" = custom ]; then
    ask "Server address" "$(current custom_url || true)"
    url="${REPLY:-http://localhost:11434/v1}"
    ask "Model (must see images, e.g. qwen2.5vl:7b, gemma3, llama3.2-vision)" "$(current custom_model || true)"
    model="${REPLY:-qwen2.5vl:7b}"
    ask_secret "API key (Enter = none, fine for Ollama / LM Studio)"
  else
    if [ "$provider" = anthropic ]; then say "$(c 2 'Get a key at console.anthropic.com -> API keys (starts with sk-ant-)')"
    else say "$(c 2 'Get a key at platform.deepseek.com -> API keys')"; fi
    ask_secret "Paste your API key (hidden; Enter = keep the saved one)"
  fi
  key="$REPLY"
  ask "Your first name (so meeting notes can find YOUR tasks)" "$(current your_name)"; local name="$REPLY"
  ask "Your course (optional)" "$(current course_context)"; local course="$REPLY"
  local triggers=(double_ctrl double_rctrl triple_ctrl right_ctrl hotkey) t_idx=1 i=1
  for t in "${triggers[@]}"; do [ "$(current trigger)" = "$t" ] && t_idx=$i; i=$((i + 1)); done
  choose "How do you want to call the buddy? (press it again to type a suggestion)" "$t_idx" \
    "Double-tap Ctrl (either one) - recommended" "Double-tap RIGHT Ctrl only" "Triple-tap Ctrl" \
    "Tap Right Ctrl once" "Ctrl + Alt + Space"
  local trigger="${triggers[$((REPLY - 1))]}"
  local efforts=(low medium high) e_idx=1
  case "$(current effort)" in medium) e_idx=2 ;; high) e_idx=3 ;; esac
  choose "Speed vs depth" "$e_idx" "Fast - answers in a few seconds (recommended)" "Balanced" "Thorough"
  local effort="${efforts[$((REPLY - 1))]}"
  local auto=false mic=false sys=false
  ask_yes "Start MoodleClicky when you log in?" "$([ "$(current start_with_windows)" = false ] && echo n || echo y)" && auto=true
  say ""; say "$(c 1 'Lecture / meeting notetaker')"
  ask_yes "Record your microphone?" "$([ "$(current record_mic)" = false ] && echo n || echo y)" && mic=true
  ask_yes "Record computer audio (Teams / Zoom / Panopto)?" "$([ "$(current record_system)" = false ] && echo n || echo y)" && sys=true
  local models=(tiny.en base.en small.en medium.en) m_idx=3 i=1
  for m in "${models[@]}"; do [ "$(current whisper_model)" = "$m" ] && m_idx=$i; i=$((i + 1)); done
  choose "Speech-to-text quality (downloads on first use)" "$m_idx" "tiny - fastest" "base - fast" \
    "small - good balance (~250 MB)" "medium - best, slow on older laptops"
  local whisper="${models[$((REPLY - 1))]}"

  step "Saving"
  # Answers go through the environment (never the command line) as JSON built by Python.
  local payload
  payload="$(MC_PROVIDER="$provider" MC_KEY="$key" MC_URL="$url" MC_MODEL="$model" MC_NAME="$name" \
    MC_COURSE="$course" MC_TRIGGER="$trigger" MC_EFFORT="$effort" MC_AUTO="$auto" MC_MIC="$mic" MC_SYS="$sys" \
    MC_WHISPER="$whisper" "$VENV/bin/python" - <<'PY'
import json, os
e = os.environ
p = {"provider": e["MC_PROVIDER"], "your_name": e["MC_NAME"], "course_context": e["MC_COURSE"],
     "trigger": e["MC_TRIGGER"], "effort": e["MC_EFFORT"], "whisper_model": e["MC_WHISPER"],
     "start_with_windows": e["MC_AUTO"] == "true", "record_mic": e["MC_MIC"] == "true",
     "record_system": e["MC_SYS"] == "true", "buddy_visible": True, "instant": True}
if e["MC_URL"]:
    p["custom_url"], p["custom_model"] = e["MC_URL"], e["MC_MODEL"]
if e["MC_KEY"].strip():
    p["api_key"] = e["MC_KEY"]
print(json.dumps(p))
PY
)"
  key=""
  MOODLECLICKY_SETUP="$payload" "$VENV/bin/python" -m moodleclicky --apply-setup \
    || { cat "$DATA/setup.log" 2>/dev/null; die "Saving settings failed."; }
  payload=""
  sed 's/^/    /' "$DATA/setup.log" 2>/dev/null | grep -v '^    OK$' || true
  say "$(c 32 'Saved.')"
}

start_app() {
  step "Starting MoodleClicky"
  if [ "${XDG_SESSION_TYPE:-}" = wayland ]; then
    say "$(c 33 "You're on Wayland. Global keys and screenshots need an X11 session:")"
    say "$(c 33 'log out, pick the Xorg / X11 session on the login screen, log back in.')"
  fi
  "$BIN"
  say "It lives in your system tray (by the clock)."
  say ""
  say "  $(c 1 'Ctrl, Ctrl')          look at what's under your mouse (again = type the suggestion)"
  say "  $(c 1 'Hold Ctrl + talk')    ask a question out loud"
  say "  $(c 1 'Ctrl + Alt + A')      move your mouse onto the answer"
  say "  $(c 1 'Ctrl + Alt + Space')  type a question"
  say "  $(c 1 'Ctrl + Alt + N')      lecture / meeting notetaker"
  say ""
  say "Settings later: tray icon → Settings, or run: moodleclicky --setup"
}

uninstall() {
  step "Uninstalling"
  stop_app
  rm -rf "$APP" "$VENV" "$BIN" "$DESKTOP" "$ICON" "$AUTOSTART"
  rmdir "$HOME_DIR" 2>/dev/null || true
  if [ -d "$DATA" ] && ! ask_yes "Keep your settings and revision notes ($DATA)?" y; then
    rm -rf "$DATA"
    say "Settings and notes removed."
  fi
  say "$(c 32 'MoodleClicky removed.')"
}

banner
case "$MODE" in
  uninstall) uninstall; exit 0 ;;
  setup) [ -x "$VENV/bin/python" ] || die "Not installed yet - run without --setup first."; setup_menu; exit 0 ;;
esac

[ "$MODE" = update ] || install_packages
pick_python || die "Needs Python 3.11+ with Tk: sudo apt install python3 python3-tk python3-venv"
say "Using $("$PY" --version) ($PY)"
stop_app
fetch_source
make_venv
make_shortcuts
if [ "$MODE" = install ] || [ ! -f "$DATA/config.json" ]; then setup_menu; fi
start_app
say "$(c 32 'All set.')"
