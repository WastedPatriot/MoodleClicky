"""Settings window (opened from the ⚙ in the pop-up or the tray icon)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from moodleclicky.brain import PRICES
from moodleclicky.config import EFFORTS, MODE_LABELS, MODES, Settings, get_api_key, set_api_key


class SettingsWindow:
    def __init__(self, root: tk.Tk, settings: Settings, on_save: Callable[[Settings], None],
                 open_notes: Callable[[], None]):
        self.settings = settings
        self.on_save = on_save
        w = self.win = tk.Toplevel(root)
        w.title("MoodleClicky settings")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)

        self.visible = tk.BooleanVar(value=settings.buddy_visible)
        ttk.Checkbutton(f, text="Show the cursor buddy", variable=self.visible).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        rows: list[tuple[str, tk.Widget]] = []
        self.key = tk.StringVar(value=get_api_key())
        key_entry = ttk.Entry(f, textvariable=self.key, show="•", width=42)
        rows.append(("Anthropic API key", key_entry))

        self.mode = tk.StringVar(value=MODE_LABELS[settings.mode])
        rows.append(("Default mode", ttk.Combobox(f, textvariable=self.mode, state="readonly", width=40,
                                                  values=[MODE_LABELS[m] for m in MODES])))
        self.model = tk.StringVar(value=settings.model)
        rows.append(("Model", ttk.Combobox(f, textvariable=self.model, width=40, values=list(PRICES))))
        self.effort = tk.StringVar(value=settings.effort)
        rows.append(("Thinking effort", ttk.Combobox(f, textvariable=self.effort, state="readonly",
                                                     width=40, values=list(EFFORTS))))
        self.course = tk.StringVar(value=settings.course_context)
        rows.append(("Your course (optional)", ttk.Entry(f, textvariable=self.course, width=42)))
        self.hk_ask = tk.StringVar(value=settings.hotkey_ask)
        rows.append(("Ask hotkey", ttk.Entry(f, textvariable=self.hk_ask, width=42)))
        self.hk_toggle = tk.StringVar(value=settings.hotkey_toggle)
        rows.append(("Show/hide hotkey", ttk.Entry(f, textvariable=self.hk_toggle, width=42)))
        self.color = tk.StringVar(value=settings.buddy_color)
        rows.append(("Buddy colour", ttk.Entry(f, textvariable=self.color, width=42)))

        for i, (label, widget) in enumerate(rows, start=1):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=3)
            widget.grid(row=i, column=1, sticky="w", pady=3)

        r = len(rows) + 1
        self.open_answer = tk.BooleanVar(value=settings.open_on_answer)
        ttk.Checkbutton(f, text="Jump straight to the answer (skip the walkthrough)",
                        variable=self.open_answer).grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.notes = tk.BooleanVar(value=settings.save_notes)
        ttk.Checkbutton(f, text="Save every explanation to my revision notes",
                        variable=self.notes).grid(row=r + 1, column=0, columnspan=2, sticky="w")
        ttk.Label(f, foreground="#777", text="Hotkeys use pynput format, e.g. <ctrl>+<alt>+<space>").grid(
            row=r + 2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        btns = ttk.Frame(f)
        btns.grid(row=r + 3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Open notes folder", command=open_notes).pack(side="left", padx=(0, 16))
        ttk.Button(btns, text="Cancel", command=w.destroy).pack(side="left", padx=4)
        ttk.Button(btns, text="Save", command=self._save).pack(side="left")
        w.bind("<Escape>", lambda _e: w.destroy())
        w.focus_force()

    def _save(self) -> None:
        s = self.settings
        s.buddy_visible = self.visible.get()
        label_to_mode = {v: k for k, v in MODE_LABELS.items()}
        s.mode = label_to_mode.get(self.mode.get(), "breakdown")
        s.model = self.model.get().strip() or "claude-opus-5-5"
        s.effort = self.effort.get() if self.effort.get() in EFFORTS else "medium"
        s.course_context = self.course.get().strip()
        s.hotkey_ask = self.hk_ask.get().strip() or s.hotkey_ask
        s.hotkey_toggle = self.hk_toggle.get().strip() or s.hotkey_toggle
        s.buddy_color = self.color.get().strip() or s.buddy_color
        s.open_on_answer = self.open_answer.get()
        s.save_notes = self.notes.get()
        if self.key.get().strip() != get_api_key():
            set_api_key(self.key.get().strip())
        s.save()
        self.on_save(s)
        self.win.destroy()
