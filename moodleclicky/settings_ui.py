"""Settings window (opened from the ⚙ in the pop-up or the tray icon)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from moodleclicky import theme as t
from moodleclicky.brain import PRICES
from moodleclicky.config import (
    DEFAULT_MODELS,
    EFFORTS,
    MODE_LABELS,
    MODES,
    WHISPER_MODELS,
    Settings,
    get_api_key,
    set_api_key,
)
from moodleclicky.triggers import TRIGGER_LABELS, TRIGGERS

KEY_HINTS = {
    "anthropic": "Get one at console.anthropic.com → API keys (starts with sk-ant-).",
    "deepseek": "Get one at platform.deepseek.com → API keys. Cheaper; needs a vision model.",
}


class SettingsWindow:
    def __init__(self, root: tk.Tk, settings: Settings, on_save: Callable[[Settings], None],
                 open_notes: Callable[[], None]):
        self.settings = s = settings
        self.on_save = on_save
        w = self.win = tk.Toplevel(root)
        w.title("MoodleClicky · Settings")
        w.attributes("-topmost", True)
        t.style_window(w)
        f = t.fonts(w)

        outer = tk.Frame(w, bg=t.BG)
        outer.pack(fill="both", expand=True, padx=16, pady=14)
        top = tk.Frame(outer, bg=t.BG)
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="Settings", bg=t.BG, fg=t.INK, font=f.display).pack(side="left")

        bar = tk.Frame(outer, bg=t.BG)
        bar.pack(fill="x", side="bottom", pady=(12, 0))
        t.PillButton(bar, "Save", self._save, kind="primary").pack(side="right")
        t.PillButton(bar, "Cancel", w.destroy, kind="ghost").pack(side="right", padx=6)
        t.PillButton(bar, "Open notes folder", open_notes).pack(side="left")

        # Fit any screen: the scroll area gets whatever the window leaves after the header and buttons.
        win_h = min(780, w.winfo_screenheight() - 90)
        scroll = t.ScrollFrame(outer, max_height=win_h - 150)
        scroll.pack(fill="both", expand=True)
        body = scroll.body

        # -- AI provider
        a = t.Card(body, "AI provider", "Use your own key. Each answer shows roughly what it cost.")
        a.pack(fill="x", pady=(0, 10))
        if not get_api_key(s.provider):
            tk.Label(a.body, text="👋  Paste a Claude or DeepSeek API key below to get started, then press Save.",
                     bg=t.ACCENT_LO, fg=t.INK, font=f.small, anchor="w", justify="left", wraplength=420,
                     padx=10, pady=8).pack(fill="x", pady=(0, 12))
        self.provider = tk.StringVar(w, s.provider)
        t.Segmented(a.body, [("anthropic", "Claude"), ("deepseek", "DeepSeek")], variable=self.provider,
                    command=lambda _v: self._show_provider()).pack(anchor="w", pady=(0, 12))
        self.keys = {p: tk.StringVar(w, get_api_key(p)) for p in ("anthropic", "deepseek")}
        self.models = {"anthropic": tk.StringVar(w, s.model), "deepseek": tk.StringVar(w, s.deepseek_model)}
        self.provider_frames = {}
        for p, label in (("anthropic", "Claude"), ("deepseek", "DeepSeek")):
            fr = tk.Frame(a.body, bg=t.CARD)
            t.form_row(fr, f"{label} API key", lambda par, p=p: t.Field(par, self.keys[p], show="•", eye=True,
                                                                        placeholder="paste your key"),
                       hint=KEY_HINTS[p])
            options = [m for m in PRICES if m.startswith("claude" if p == "anthropic" else "deepseek")]
            t.form_row(fr, "Model", lambda par, p=p, o=options: t.combobox(par, self.models[p], o),
                       hint=f"Default: {DEFAULT_MODELS[p]}")
            self.provider_frames[p] = fr
        self.effort = tk.StringVar(w, s.effort)
        self.effort_row = t.form_row(a.body, "Speed vs depth", lambda p: t.Segmented(
            p, [("low", "Fast"), ("medium", "Balanced"), ("high", "Thorough")], variable=self.effort),
            hint="Fast replies in a few seconds. Thorough thinks longer for hard problems.", pady=(4, 0))
        self._show_provider()

        # -- General
        g = t.Card(body, "General", "How the buddy behaves.")
        g.pack(fill="x", pady=(0, 10))
        self.trigger = tk.StringVar(w, TRIGGER_LABELS.get(s.trigger, TRIGGER_LABELS["double_rctrl"]))
        t.form_row(g.body, "Wake-up key", lambda p: t.combobox(
            p, self.trigger, [TRIGGER_LABELS[k] for k in TRIGGERS], readonly=True),
            hint="Tapping Ctrl on its own does nothing in browsers or Word, and Ctrl+C / Ctrl+V don't count. "
                 "Press it again to type a suggestion into your box. Right Ctrl avoids PowerToys' Find My Mouse "
                 "(Left Ctrl ×2).")
        self.instant = tk.BooleanVar(w, s.instant)
        t.Toggle(g.body, self.instant, "Look straight away", "Off = ask \"what are you stuck on?\" first").pack(
            fill="x", pady=(0, 10))
        self.compact = tk.BooleanVar(w, s.compact)
        t.Toggle(g.body, self.compact, "Speech bubble by the cursor",
                 "Small Clicky-style text that talks you through it and fades; clicks go straight through. "
                 "Off = the big card.").pack(fill="x", pady=(0, 10))
        self.visible = tk.BooleanVar(w, s.buddy_visible)
        t.Toggle(g.body, self.visible, "Show the cursor buddy", "Ctrl+Alt+H or the tray icon also toggles it").pack(
            fill="x", pady=(0, 10))
        self.mode = tk.StringVar(w, MODE_LABELS[s.mode])
        t.form_row(g.body, "Start in this mode", lambda p: t.Segmented(
            p, [(MODE_LABELS[m], m.capitalize()) for m in MODES], variable=self.mode),
            hint="Breakdown = answer + steps · Hint = no spoilers · Check = marks your working")
        self.open_answer = tk.BooleanVar(w, s.open_on_answer)
        t.Toggle(g.body, self.open_answer, "Jump straight to the answer", "Skip the walkthrough").pack(
            fill="x", pady=(0, 10))
        self.course = tk.StringVar(w, s.course_context)
        t.form_row(g.body, "Your course (optional)", lambda p: t.Field(p, self.course,
                   placeholder="e.g. Birkbeck BSc Computer Science, Year 2"),
                   hint="Helps explanations match your level and module names.")
        self.color = tk.StringVar(w, s.buddy_color)
        t.form_row(g.body, "Buddy colour", lambda p: t.Field(p, self.color, placeholder="#2f80ed"))
        self.autostart = tk.BooleanVar(w, s.start_with_windows)
        t.Toggle(g.body, self.autostart, "Start with Windows", "Sits quietly in the tray after you log in").pack(
            fill="x")

        # -- Notetaker
        n = t.Card(body, "Lecture notetaker", "Records, transcribes on this PC, then the AI makes notes.")
        n.pack(fill="x", pady=(0, 10))
        self.rec_mic = tk.BooleanVar(w, s.record_mic)
        t.Toggle(n.body, self.rec_mic, "Record my microphone", "In-person lectures and group meetings").pack(
            fill="x", pady=(0, 8))
        self.rec_system = tk.BooleanVar(w, s.record_system)
        t.Toggle(n.body, self.rec_system, "Record computer audio", "Teams, Zoom, Panopto, YouTube").pack(
            fill="x", pady=(0, 10))
        self.whisper = tk.StringVar(w, s.whisper_model)
        t.form_row(n.body, "Speech-to-text model", lambda p: t.combobox(p, self.whisper, WHISPER_MODELS,
                                                                        readonly=True),
                   hint="small.en = good balance. First use downloads it (~250 MB).")
        self.name = tk.StringVar(w, s.your_name)
        t.form_row(n.body, "Your name", lambda p: t.Field(p, self.name, placeholder="e.g. Dom"),
                   hint="So group-meeting notes can pull out your tasks.", pady=(0, 0))

        # -- Hotkeys
        h = t.Card(body, "Hotkeys", "pynput format, e.g. <ctrl>+<alt>+<space>")
        h.pack(fill="x", pady=(0, 10))
        self.hk = {}
        for key, label in (("hotkey_ask", "Ask about my screen"), ("hotkey_toggle", "Show / hide buddy"),
                           ("hotkey_notes", "Open notetaker"), ("hotkey_mark", "Mark important moment")):
            self.hk[key] = tk.StringVar(w, getattr(s, key))
            t.form_row(h.body, label, lambda p, k=key: t.Field(p, self.hk[k]), pady=(0, 8))

        # -- Notes
        nn = t.Card(body, "Revision notes")
        nn.pack(fill="x")
        self.notes = tk.BooleanVar(w, s.save_notes)
        t.Toggle(nn.body, self.notes, "Save every explanation to my notes", "One Markdown file per day").pack(
            fill="x")

        w.bind("<Escape>", lambda _e: w.destroy())
        w.update_idletasks()
        w.geometry(f"540x{win_h}+{max(0, (w.winfo_screenwidth() - 540) // 2)}+20")
        w.minsize(460, 360)
        self.scroll = scroll
        w.focus_force()

    def _show_provider(self) -> None:
        for fr in self.provider_frames.values():
            fr.pack_forget()
        self.provider_frames[self.provider.get()].pack(fill="x", before=self.effort_row.master)

    def _save(self) -> None:
        s = self.settings
        s.buddy_visible = self.visible.get()
        s.trigger = {v: k for k, v in TRIGGER_LABELS.items()}.get(self.trigger.get(), "double_rctrl")
        s.instant = self.instant.get()
        s.compact = self.compact.get()
        label_to_mode = {v: k for k, v in MODE_LABELS.items()}
        s.mode = label_to_mode.get(self.mode.get(), "breakdown")
        s.provider = self.provider.get() if self.provider.get() in ("anthropic", "deepseek") else "anthropic"
        s.model = self.models["anthropic"].get().strip() or DEFAULT_MODELS["anthropic"]
        s.deepseek_model = self.models["deepseek"].get().strip() or DEFAULT_MODELS["deepseek"]
        s.effort = self.effort.get() if self.effort.get() in EFFORTS else "low"
        s.course_context = self.course.get().strip()
        for key, var in self.hk.items():
            setattr(s, key, var.get().strip() or getattr(s, key))
        s.buddy_color = self.color.get().strip() or s.buddy_color
        s.open_on_answer = self.open_answer.get()
        s.save_notes = self.notes.get()
        s.start_with_windows = self.autostart.get()
        s.record_mic = self.rec_mic.get()
        s.record_system = self.rec_system.get()
        s.whisper_model = self.whisper.get() if self.whisper.get() in WHISPER_MODELS else "small.en"
        s.your_name = self.name.get().strip()
        for p, var in self.keys.items():
            if var.get().strip() != get_api_key(p):
                set_api_key(var.get().strip(), p)
        s.save()
        self.on_save(s)
        self.win.destroy()
