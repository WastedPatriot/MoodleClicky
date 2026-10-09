"""The notetaker panel: record a lecture or group meeting, watch the live transcript, catch up, make notes."""

from __future__ import annotations

import re
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import datetime

from moodleclicky import theme as t
from moodleclicky.brain import APIProblem
from moodleclicky.config import Settings
from moodleclicky.lecture import summarise
from moodleclicky.lecture.session import Session, recent_sessions
from moodleclicky.lecture.transcribe import fmt_time
from moodleclicky.notes import notes_dir


class NotetakerWindow:
    def __init__(self, root: tk.Misc, settings: Settings, call_soon: Callable[[Callable[[], None]], None],
                 open_path: Callable[[str], None], session_factory: Callable[..., Session] | None = None):
        self.root = root
        self.settings = settings
        self.call_soon = call_soon
        self.open_path = open_path
        self.session_factory = session_factory or Session
        self.session: Session | None = None
        self.busy = False
        self._shown_segments = 0

        w = self.win = tk.Toplevel(root)
        w.title("MoodleClicky · Notetaker")
        w.geometry("460x760")
        w.minsize(420, 640)
        t.style_window(w)
        w.protocol("WM_DELETE_WINDOW", self.hide)
        f = t.fonts(w)

        outer = tk.Frame(w, bg=t.BG)
        outer.pack(fill="both", expand=True, padx=16, pady=14)

        head = tk.Frame(outer, bg=t.BG)
        head.pack(fill="x")
        tk.Label(head, text="Notetaker", bg=t.BG, fg=t.INK, font=f.display, anchor="w").pack(side="left")
        self.kind = tk.StringVar(w, "lecture")
        self.kind_ctl = t.Segmented(head, [("lecture", "Lecture"), ("meeting", "Group meeting")],
                                    variable=self.kind, width=240)
        self.kind_ctl.pack(side="right")

        # -- recorder card
        rec = t.Card(outer)
        rec.pack(fill="x", pady=(12, 0))
        row = tk.Frame(rec.body, bg=t.CARD)
        row.pack(fill="x")
        self.dot = tk.Canvas(row, width=14, height=14, bg=t.CARD, highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 8))
        self.clock = tk.Label(row, text="00:00", bg=t.CARD, fg=t.INK, font=(f.family, 22, "bold"))
        self.clock.pack(side="left")
        self.meter = tk.Canvas(row, width=120, height=10, bg=t.CARD, highlightthickness=0)
        self.meter.pack(side="right", pady=8)
        self.status = tk.Label(rec.body, text="Ready.", bg=t.CARD, fg=t.MUTED, font=f.small, anchor="w",
                               justify="left", wraplength=380)
        self.status.pack(fill="x", pady=(6, 10))

        btns = tk.Frame(rec.body, bg=t.CARD)
        btns.pack(fill="x")
        self.start_btn = t.PillButton(btns, "●  Start recording", self.start, kind="primary")
        self.start_btn.pack(side="left")
        self.pause_btn = t.PillButton(btns, "Pause", self.pause_resume)
        self.stop_btn = t.PillButton(btns, "Stop", self.stop, kind="danger")
        self.mark_btn = t.PillButton(btns, "⭐ Mark", self.mark, kind="ghost",
                                     tooltip="Flag this moment as important (Ctrl+Alt+M)")

        srcs = tk.Frame(rec.body, bg=t.CARD)
        srcs.pack(fill="x", pady=(12, 0))
        self.mic = tk.BooleanVar(w, settings.record_mic)
        self.system = tk.BooleanVar(w, settings.record_system)
        t.Toggle(srcs, self.mic, "Microphone", "the room / your group",
                 command=lambda v: self._set_source("record_mic", v)).pack(fill="x", pady=(0, 6))
        t.Toggle(srcs, self.system, "Computer audio", "Teams, Zoom, Panopto, YouTube",
                 command=lambda v: self._set_source("record_system", v)).pack(fill="x")

        # -- catch up
        cu = t.Card(outer, "Zoned out?", "Get the last few minutes in 10 seconds.")
        cu.pack(fill="x", pady=(10, 0))
        crow = tk.Frame(cu.body, bg=t.CARD)
        crow.pack(fill="x")
        self.minutes = tk.StringVar(w, "5")
        t.Segmented(crow, [("2", "2 min"), ("5", "5 min"), ("10", "10 min")], variable=self.minutes).pack(
            side="left")
        self.catch_btn = t.PillButton(crow, "Catch me up", self.catch_up, kind="primary")
        self.catch_btn.pack(side="right")

        # -- live transcript
        self.transcript_label = tk.Label(outer, text="LIVE TRANSCRIPT", bg=t.BG, fg=t.SUBTLE, font=f.tiny_bold,
                                         anchor="w")
        self.transcript_label.pack(fill="x", pady=(12, 4))
        self.text = tk.Text(outer, height=5, wrap="word")
        t.style_text(self.text, bg=t.CARD)
        self.text.configure(padx=10, pady=8, state="disabled")
        self.text.tag_configure("time", foreground=t.SUBTLE, font=f.tiny)
        self.text.pack(fill="both", expand=True)

        # -- footer
        foot = tk.Frame(outer, bg=t.BG)
        self.notes_btn = t.PillButton(foot, "✨ Make notes", self.make_notes, kind="primary")
        self.notes_btn.pack(side="left")
        self.past = tk.StringVar(w, "")
        self._past_map: dict[str, object] = {}
        self.past_box = t.combobox(foot, self.past, [], readonly=True, width=18)
        self.past_box.pack(side="right")
        self.past_box.bind("<<ComboboxSelected>>", lambda _e: self.load_past())
        self.past_box.bind("<Button-1>", lambda _e: self._refresh_past())
        tk.Label(foot, text="Past:", bg=t.BG, fg=t.MUTED, font=f.small).pack(side="right", padx=(0, 6))
        consent = tk.Label(outer, text="Only record where you're allowed to, and tell your group first. "
                                       "Audio is transcribed on this PC and then deleted.",
                           bg=t.BG, fg=t.SUBTLE, font=f.tiny, anchor="w", justify="left", wraplength=420)
        # Footer + consent line are packed from the bottom so the transcript box gives way, not the buttons.
        consent.pack(side="bottom", fill="x", pady=(8, 0))
        foot.pack(side="bottom", fill="x", pady=(10, 0))
        self.text.pack_forget()
        self.text.pack(fill="both", expand=True)

        self._refresh_past()
        self.refresh()
        self._tick()

    # ---- window --------------------------------------------------------
    def show(self) -> None:
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def hide(self) -> None:
        self.win.withdraw()  # recording carries on in the background

    # ---- actions -------------------------------------------------------
    def start(self) -> None:
        if self.session and self.session.state in ("recording", "paused"):
            return
        if not (self.mic.get() or self.system.get()):
            self._say("Turn on the microphone and/or computer audio first.")
            return
        self.session = self.session_factory(self.settings, self.kind.get(),
                                            on_update=lambda: self.call_soon(self.refresh))
        self._shown_segments = 0
        self._clear_text()
        try:
            self.session.start()
        except Exception as e:  # no audio device, missing package, etc.
            self.session = None
            self._say(f"Couldn't start recording: {e}")
            return
        self.refresh()

    def pause_resume(self) -> None:
        if not self.session:
            return
        if self.session.state == "recording":
            self.session.pause()
        elif self.session.state == "paused":
            self.session.resume()
        self.refresh()

    def stop(self) -> None:
        if self.session:
            self.session.stop()
            self.refresh()

    def mark(self) -> None:
        if self.session and self.session.state in ("recording", "paused"):
            at = self.session.mark()
            self._say(f"⭐ Marked {fmt_time(at)} - it'll be highlighted in your notes.")

    def catch_up(self) -> None:
        s = self.session
        if not s or not s.segments:
            self._say("Nothing transcribed yet - give it 30 seconds after you start.")
            return
        minutes = int(self.minutes.get() or 5)
        self._run_ai("Catching you up…", lambda: summarise.catch_up(
            self.settings, s.kind, list(s.segments), s.elapsed(), minutes), self._show_catch_up)

    def make_notes(self) -> None:
        s = self.session
        if not s or not s.segments:
            self._say("Record something (or pick a past session) first.")
            return
        if s.backlog:
            self._say(f"Still transcribing {s.backlog} chunk(s) - notes will include what's done so far.")
        self._run_ai("Writing your notes…", lambda: summarise.make_notes(
            self.settings, s.kind, list(s.segments), list(s.markers)), self._show_notes)

    def load_past(self) -> None:
        folder = self._past_map.get(self.past.get())
        if not folder:
            return
        if self.session and self.session.state in ("recording", "paused", "finishing"):
            self._say("Stop the current recording first.")
            return
        try:
            self.session = Session.load(folder, self.settings)
        except (OSError, ValueError, KeyError) as e:
            self._say(f"Couldn't open that session: {e}")
            return
        self.kind.set(self.session.kind)
        self._shown_segments = 0
        self._clear_text()
        self.refresh()
        notes = folder / "notes.md"
        if notes.exists():
            self._say(f"Loaded {self.past.get()} - notes already made, opening them.")
            self.open_path(str(notes))

    # ---- AI helpers ----------------------------------------------------
    def _run_ai(self, msg: str, job: Callable[[], dict], done: Callable[[dict], None]) -> None:
        if self.busy:
            return
        self.busy = True
        self._say(msg)
        self.catch_btn.config(state="disabled")
        self.notes_btn.config(state="disabled")

        def work():
            try:
                res = job()
                self.call_soon(lambda: done(res))
            except APIProblem as e:
                err = str(e)
                self.call_soon(lambda: self._say(err))
            except Exception as e:  # never kill the panel
                err = f"Something went wrong: {e}"
                self.call_soon(lambda: self._say(err))
            finally:
                self.call_soon(self._ai_done)

        threading.Thread(target=work, daemon=True).start()

    def _ai_done(self) -> None:
        self.busy = False
        self.catch_btn.config(state="normal")
        self.notes_btn.config(state="normal")

    def _show_catch_up(self, data: dict) -> None:
        self._say(f"Caught up (≈ ${data.get('_cost_usd', 0):.3f})")
        NotesViewer(self.win, "What you missed", summarise.catchup_text(data))

    def _show_notes(self, data: dict) -> None:
        s = self.session
        md = summarise.notes_markdown(s.kind, data, f"{s.started:%a %d %b %Y, %H:%M}",
                                      fmt_time(s.elapsed()))
        path = s.save_notes(md)
        title = re.sub(r"[^\w\- ]+", "", data.get("title") or s.kind).strip()[:60] or s.kind
        copy = notes_dir() / f"{s.started:%Y-%m-%d} {title}.md"
        try:
            copy.write_text(md, encoding="utf-8")
        except OSError:
            copy = path
        self._say(f"Notes saved (≈ ${data.get('_cost_usd', 0):.3f}) → {copy.name}")
        NotesViewer(self.win, data.get("title") or "Notes", md, on_open=lambda: self.open_path(str(copy)))

    # ---- refresh -------------------------------------------------------
    def refresh(self) -> None:
        s = self.session
        state = s.state if s else "idle"
        recording = state in ("recording", "paused")
        for b in (self.pause_btn, self.stop_btn, self.mark_btn):
            b.pack_forget()
        if recording:
            self.start_btn.pack_forget()
            self.pause_btn.config(text="Resume" if state == "paused" else "Pause")
            self.pause_btn.pack(side="left")
            self.stop_btn.pack(side="left", padx=6)
            self.mark_btn.pack(side="right")
        elif not self.start_btn.winfo_ismapped():
            self.start_btn.pack(side="left")
        self.start_btn.config(text="●  New recording" if s else "●  Start recording")
        if s:
            bits = [s.status] if s.status else []
            if s.recorder is not None and recording:
                bits.append(s.recorder.status())
            if s.backlog:
                bits.append(f"transcribing… {s.backlog} behind")
            if state == "done":
                bits = [f"Done · {len(s.segments)} lines · {fmt_time(s.elapsed())}"]
            self.status.config(text="  ·  ".join(b for b in bits if b))
            self._append_segments()
        self._draw_dot(state)

    def _tick(self) -> None:
        try:
            s = self.session
            if s and s.state in ("recording", "paused"):
                self.clock.config(text=fmt_time(s.elapsed()))
                lvl = s.recorder.level if s.recorder is not None and s.state == "recording" else 0
                self._draw_meter(lvl)
                self._draw_dot(s.state)
            else:
                self._draw_meter(0)
            self.win.after(200, self._tick)
        except tk.TclError:
            pass

    def _append_segments(self) -> None:
        s = self.session
        if not s or self._shown_segments >= len(s.segments):
            return
        new = s.segments[self._shown_segments:]
        self._shown_segments = len(s.segments)
        self.text.configure(state="normal")
        for seg in new:
            self.text.insert("end", f"{fmt_time(seg.start)}  ", ("time",))
            self.text.insert("end", seg.text + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def _clear_text(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def _draw_dot(self, state: str) -> None:
        c = self.dot
        c.delete("all")
        color = {"recording": t.DANGER, "paused": t.WARN, "finishing": t.ACCENT, "done": t.SUCCESS}.get(
            state, t.SUBTLE)
        if state == "recording" and int(datetime.now().timestamp() * 2) % 2:
            color = t.mix(c, t.DANGER, t.CARD, 0.5)
        c.create_oval(2, 2, 12, 12, fill=color, outline="")

    def _draw_meter(self, level: float) -> None:
        c = self.meter
        c.delete("all")
        t.round_rect(c, 0, 0, 120, 10, 5, fill=t.SURFACE, outline="")
        if level > 0.01:
            w = max(10, int(120 * min(1.0, level)))
            t.round_rect(c, 0, 0, w, 10, 5, fill=t.SUCCESS if level < 0.85 else t.WARN, outline="")

    def _say(self, msg: str) -> None:
        self.status.config(text=msg)

    def _set_source(self, key: str, value: bool) -> None:
        setattr(self.settings, key, value)
        self.settings.save()

    def _refresh_past(self) -> None:
        self._past_map = {}
        for d in recent_sessions():
            label = d.name.replace("_", " ")
            self._past_map[label] = d
        self.past_box.configure(values=list(self._past_map))


class NotesViewer:
    """A simple dark window showing Markdown-ish notes, with Copy / Open buttons."""

    def __init__(self, parent: tk.Misc, title: str, text: str, on_open: Callable[[], None] | None = None):
        w = self.win = tk.Toplevel(parent)
        w.title(title)
        w.geometry("560x620")
        t.style_window(w)
        f = t.fonts(w)
        body = tk.Frame(w, bg=t.BG)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        bar = tk.Frame(body, bg=t.BG)
        bar.pack(fill="x", side="bottom", pady=(10, 0))
        t.PillButton(bar, "Copy", self.copy).pack(side="left")
        if on_open:
            t.PillButton(bar, "Open file", on_open).pack(side="left", padx=6)
        t.PillButton(bar, "Close", w.destroy, kind="ghost").pack(side="right")
        self.text = tk.Text(body, wrap="word")
        t.style_text(self.text, bg=t.CARD)
        self.text.configure(padx=14, pady=12)
        self.text.tag_configure("h1", font=f.display, spacing3=6)
        self.text.tag_configure("h2", font=f.title, foreground=t.ACCENT_HI, spacing1=10)
        self.text.tag_configure("muted", foreground=t.MUTED)
        self.text.pack(fill="both", expand=True)
        self.raw = text
        for line in text.splitlines():
            if line.startswith("# "):
                self.text.insert("end", line[2:] + "\n", ("h1",))
            elif line.startswith("## "):
                self.text.insert("end", line[3:] + "\n", ("h2",))
            elif line.startswith("> ") or (line.startswith("*") and line.endswith("*") and len(line) > 2):
                self.text.insert("end", line.strip("*> ") + "\n", ("muted",))
            else:
                self._inline(line.replace("- [ ] ", "☐ ").replace("- ", "• ", 1) + "\n")
        self.text.configure(state="disabled")
        w.lift()

    def _inline(self, line: str) -> None:
        """**bold** and *muted italics* inside a line."""
        for part in re.split(r"(\*\*.+?\*\*|\*[^*]+\*)", line):
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                self.text.insert("end", part[2:-2], ("b",))
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                self.text.insert("end", part[1:-1], ("muted",))
            else:
                self.text.insert("end", part)

    def copy(self) -> None:
        self.win.clipboard_clear()
        self.win.clipboard_append(self.raw)
