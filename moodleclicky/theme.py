"""Shared look for every MoodleClicky window: palette, fonts and a few flat widgets (Tkinter only).

Quick tour (all widgets take the parent's background automatically so anti-aliased edges blend in):

    from moodleclicky import theme as t
    f = t.fonts(root)                               # f.title / f.body / f.small / f.tiny / f.bold / f.mono ...
    t.style_window(win)                             # dark bg + ttk styles (+ rounded corners on Windows 11)
    card = t.Card(parent, "Section title", "optional subtitle"); card.body  # pack/grid your rows into .body
    t.PillButton(card.body, "Save", command, kind="primary")  # primary | secondary | ghost | icon | danger
    t.Segmented(parent, [("a", "Option A"), ("b", "Option B")], variable=string_var)
    t.Toggle(parent, bool_var, "Label", "optional hint")
    t.Field(parent, string_var, placeholder="Type here…", show="•", eye=True)  # .entry is the tk.Entry
    t.style_text(text_widget)                       # dark text area + code/inline-code/bold tags
    t.ScrollFrame(parent)                           # .body is a frame that scrolls with the mouse wheel
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable, Sequence
from tkinter import ttk
from types import SimpleNamespace

from moodleclicky.winutil import IS_WIN

# ---- palette (dark, neutral with a blue accent) ---------------------------
BG = "#16171b"  # window background
CARD = "#1f2026"  # bubble / card surface
SURFACE = "#26272e"  # raised controls, segmented track
SURFACE_HI = "#30323a"  # hover
FIELD = "#2a2b32"  # text inputs
BORDER = "#383a43"
BORDER_HI = "#4a4d58"
INK = "#eceef3"
MUTED = "#a3a8b4"
SUBTLE = "#6e7381"
ACCENT = "#4f8cff"
ACCENT_HI = "#6c9fff"
ACCENT_LO = "#2c4f8f"
ACCENT_INK = "#ffffff"
SUCCESS = "#3ecf8e"
WARN = "#f5b94f"
VIOLET = "#b694ff"
DANGER = "#ff6b6b"
CODE_BG = "#121318"
CODE_INK = "#d9dce3"
ICODE_BG = "#2d2f37"
ICODE_INK = "#ffcd8a"

UI_FAMILIES = ("Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "Ubuntu",
               "Noto Sans", "DejaVu Sans")
MONO_FAMILIES = ("Cascadia Mono", "Cascadia Code", "Consolas", "JetBrains Mono", "SF Mono", "Menlo",
                 "Ubuntu Mono", "DejaVu Sans Mono")

_fonts: SimpleNamespace | None = None


def _pick(root: tk.Misc, wanted: Sequence[str], fallback: str) -> str:
    try:
        have = {f.lower(): f for f in tkfont.families(root)}
    except tk.TclError:
        return fallback
    for name in wanted:
        if name.lower() in have:
            return have[name.lower()]
    return fallback


def fonts(root: tk.Misc) -> SimpleNamespace:
    """Font tuples for the best UI / mono families installed (Segoe UI Variable on Windows 11)."""
    global _fonts
    if _fonts is None:
        ui = _pick(root, UI_FAMILIES, "TkDefaultFont")
        mono = _pick(root, MONO_FAMILIES, "TkFixedFont")
        _fonts = SimpleNamespace(
            family=ui, mono_family=mono,
            display=(ui, 15, "bold"),
            title=(ui, 12, "bold"),
            body=(ui, 11),
            bold=(ui, 11, "bold"),
            small=(ui, 10),
            small_bold=(ui, 10, "bold"),
            tiny=(ui, 9),
            tiny_bold=(ui, 8, "bold"),
            mono=(mono, 10),
            icon=(ui, 11),
        )
    return _fonts


def measure_line(text: tk.Text) -> int:
    """Pixel height of one line of body text in a Text widget (for auto-sizing)."""
    fobj = tkfont.Font(root=text, font=text.cget("font"))
    return fobj.metrics("linespace")  # Text `height` is measured in plain font lines


def measure(root: tk.Misc, font, text: str) -> int:
    return _font_obj(root, font).measure(text)


_font_objs: dict = {}


def _font_obj(root: tk.Misc, font) -> tkfont.Font:
    key = tuple(font) if isinstance(font, list | tuple) else font
    if key not in _font_objs:
        _font_objs[key] = tkfont.Font(root=root, font=font)
    return _font_objs[key]


# ---- colour helpers -------------------------------------------------------
def to_rgb(widget: tk.Misc, color: str) -> tuple[int, int, int]:
    """Any Tk colour (name or #hex) -> 0..255 RGB."""
    if color.startswith("#") and len(color) == 7:
        return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    r, g, b = widget.winfo_rgb(color)
    return r >> 8, g >> 8, b >> 8


def mix(widget: tk.Misc, a: str, b: str, t: float) -> str:
    """Blend colour a toward b by t (0..1)."""
    ra, ga, ba = to_rgb(widget, a)
    rb, gb, bb = to_rgb(widget, b)
    r, g, b_ = (round(ra + (rb - ra) * t), round(ga + (gb - ga) * t), round(ba + (bb - ba) * t))
    return f"#{r:02x}{g:02x}{b_:02x}"


# ---- shapes ---------------------------------------------------------------
def rounded_points(x0: float, y0: float, x1: float, y1: float, r: float,
                   tail: tuple[str, float, float, float] | None = None, segs: int = 6) -> list[float]:
    """Polygon (flat coords) for a rounded rectangle, optionally with a speech-bubble tail.

    tail = (side, offset, base_width, height): side is top|right|bottom|left, offset is the tail's centre along
    that edge measured from the edge's top/left end, and the tip sticks out `height` px beyond the edge.
    """
    import math

    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts: list[float] = []

    def arc(cx, cy, a0):
        for i in range(segs + 1):
            a = math.radians(a0 + 90 * i / segs)
            pts.extend((cx + r * math.cos(a), cy + r * math.sin(a)))

    def add_tail(side):
        if not tail or tail[0] != side:
            return
        _, off, bw, th = tail
        hb = bw / 2
        if side == "top":
            pts.extend((x0 + off - hb, y0, x0 + off, y0 - th, x0 + off + hb, y0))
        elif side == "right":
            pts.extend((x1, y0 + off - hb, x1 + th, y0 + off, x1, y0 + off + hb))
        elif side == "bottom":
            pts.extend((x0 + off + hb, y1, x0 + off, y1 + th, x0 + off - hb, y1))
        else:
            pts.extend((x0, y0 + off + hb, x0 - th, y0 + off, x0, y0 + off - hb))

    arc(x0 + r, y0 + r, 180)
    add_tail("top")
    arc(x1 - r, y0 + r, 270)
    add_tail("right")
    arc(x1 - r, y1 - r, 0)
    add_tail("bottom")
    arc(x0 + r, y1 - r, 90)
    add_tail("left")
    return pts


def round_rect(canvas: tk.Canvas, x0, y0, x1, y1, r, **kw) -> int:
    """Draw a (non anti-aliased) rounded rectangle polygon on a canvas."""
    return canvas.create_polygon(rounded_points(x0, y0, x1, y1, r), **kw)


_img_cache: dict = {}


def pill_image(widget: tk.Misc, w: int, h: int, r: int, fill: str, bg: str, outline: str | None = None):
    """Anti-aliased rounded-rect PhotoImage (Pillow, 4x supersampled), blended onto `bg`. None if unavailable."""
    key = (w, h, r, fill, bg, outline)
    if key in _img_cache:
        return _img_cache[key]
    try:
        from PIL import Image, ImageDraw, ImageTk

        s = 4
        img = Image.new("RGB", (w * s, h * s), to_rgb(widget, bg))
        d = ImageDraw.Draw(img)
        if outline:
            d.rounded_rectangle((0, 0, w * s - 1, h * s - 1), r * s, fill=to_rgb(widget, outline))
            d.rounded_rectangle((s, s, w * s - 1 - s, h * s - 1 - s), max(0, r - 1) * s, fill=to_rgb(widget, fill))
        else:
            d.rounded_rectangle((0, 0, w * s - 1, h * s - 1), r * s, fill=to_rgb(widget, fill))
        photo = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS), master=widget)
    except Exception:
        photo = None
    if len(_img_cache) > 400:
        _img_cache.clear()
    _img_cache[key] = photo
    return photo


def draw_pill(canvas: tk.Canvas, x0: int, y0: int, x1: int, y1: int, r: int, fill: str, bg: str,
              outline: str | None = None, tags: str = "") -> None:
    """Smooth rounded rect if Pillow is around, else a plain polygon."""
    w, h = int(x1 - x0), int(y1 - y0)
    if w <= 0 or h <= 0:
        return
    img = pill_image(canvas, w, h, r, fill, bg, outline)
    if img is not None:
        canvas.create_image(x0, y0, image=img, anchor="nw", tags=tags)
        refs = getattr(canvas, "_mc_imgs", None)
        if refs is None:
            refs = canvas._mc_imgs = []  # type: ignore[attr-defined]
        refs.append(img)
        del refs[:-24]
    else:
        round_rect(canvas, x0, y0, x1 - 1, y1 - 1, r, fill=fill, outline=outline or fill, tags=tags)


# ---- Windows niceties -----------------------------------------------------
def round_corners(win: tk.Misc, small: bool = False) -> None:
    """Windows 11: ask DWM for rounded window corners. Silently ignored elsewhere / on Windows 10."""
    if not IS_WIN:
        return
    try:
        import ctypes

        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        pref = ctypes.c_int(3 if small else 2)  # DWMWCP_ROUND / ROUNDSMALL
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:  # nosec B110 - cosmetic only
        pass


def dark_title_bar(win: tk.Misc) -> None:
    """Windows 10/11: dark title bar for normal (decorated) windows."""
    if not IS_WIN:
        return
    try:
        import ctypes

        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        on = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new, old)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), ctypes.sizeof(on)) == 0:
                break
    except Exception:  # nosec B110 - cosmetic only
        pass


def style_window(win: tk.Toplevel | tk.Tk) -> None:
    """Dark background, ttk styles, dark title bar + rounded corners where the OS supports them."""
    win.configure(bg=BG)
    style_ttk(win)
    dark_title_bar(win)
    round_corners(win)


def style_ttk(widget: tk.Misc) -> ttk.Style:
    """Dark 'MC.*' ttk styles (Combobox, Scrollbar). Switches the ttk theme to 'clam' so colours apply."""
    f = fonts(widget)
    st = ttk.Style(widget)
    if st.theme_use() != "clam":
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
    st.configure("MC.TCombobox", fieldbackground=FIELD, background=FIELD, foreground=INK, arrowcolor=MUTED,
                 bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD, insertcolor=INK, padding=(8, 5),
                 selectbackground=FIELD, selectforeground=INK, arrowsize=14)
    st.map("MC.TCombobox",
           fieldbackground=[("readonly", FIELD), ("disabled", SURFACE)],
           foreground=[("disabled", SUBTLE)],
           bordercolor=[("focus", ACCENT), ("hover", BORDER_HI)],
           lightcolor=[("focus", FIELD)], darkcolor=[("focus", FIELD)],
           background=[("active", SURFACE_HI), ("pressed", SURFACE_HI)],
           arrowcolor=[("hover", INK)])
    st.configure("MC.Vertical.TScrollbar", background=SURFACE, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED,
                 lightcolor=SURFACE, darkcolor=SURFACE, gripcount=0, arrowsize=12)
    st.map("MC.Vertical.TScrollbar", background=[("active", SURFACE_HI)])
    root = widget.winfo_toplevel()
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", INK)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", ACCENT_INK)
    root.option_add("*TCombobox*Listbox.font", f.body)
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    return st


def combobox(parent: tk.Misc, variable: tk.StringVar, values: Sequence[str], readonly: bool = False,
             width: int = 24) -> ttk.Combobox:
    cb = ttk.Combobox(parent, textvariable=variable, values=list(values), style="MC.TCombobox", width=width,
                      state="readonly" if readonly else "normal", font=fonts(parent).body)
    return cb


# ---- widgets --------------------------------------------------------------
def _bg_of(parent: tk.Misc) -> str:
    try:
        return str(parent.cget("bg"))
    except tk.TclError:
        return BG


class PillButton(tk.Canvas):
    """Flat rounded button with hover/press/disabled states. `.config(text=..., state=..., command=...)` work.

    kind: primary (accent), secondary (raised grey), ghost (text only until hovered), icon (small square
    glyph button), danger.
    """

    KINDS = {
        # kind: (fill, hover, pressed, text, disabled_fill, disabled_text)
        "primary": (ACCENT, ACCENT_HI, ACCENT_LO, ACCENT_INK, SURFACE, SUBTLE),
        "secondary": (SURFACE_HI, "#3a3c45", SURFACE, INK, SURFACE, SUBTLE),
        "ghost": (None, SURFACE_HI, SURFACE, MUTED, None, SUBTLE),
        "icon": (None, SURFACE_HI, SURFACE, MUTED, None, SUBTLE),
        "danger": ("#4a2327", "#5c2a30", "#3a1c20", DANGER, SURFACE, SUBTLE),
    }

    def __init__(self, parent: tk.Misc, text: str = "", command: Callable[[], None] | None = None,
                 kind: str = "secondary", font=None, height: int | None = None, width: int | None = None,
                 padx: int = 14, radius: int | None = None, bg: str | None = None, tooltip: str = ""):
        self._bg = bg or _bg_of(parent)
        self._measure_on = parent  # measure text via the parent: this canvas doesn't exist yet in __init__
        self._kind = kind
        self._text = text
        self._command = command
        self._font = font or (fonts(parent).icon if kind == "icon" else fonts(parent).small_bold)
        self._h = height or (26 if kind == "icon" else 30)
        self._fixed_w = width or (self._h if kind == "icon" else None)
        self._padx = padx
        self._radius = radius
        self._state = "normal"
        self._hover = self._down = False
        super().__init__(parent, height=self._h, width=self._width(), bg=self._bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=0)
        self.bind("<Enter>", lambda _e: self._set(hover=True))
        self.bind("<Leave>", lambda _e: self._set(hover=False, down=False))
        self.bind("<ButtonPress-1>", lambda _e: self._set(down=True))
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _width(self) -> int:
        if self._fixed_w:
            return self._fixed_w
        return measure(self._measure_on, self._font, self._text) + 2 * self._padx

    def _set(self, hover: bool | None = None, down: bool | None = None) -> None:
        if hover is not None:
            self._hover = hover
        if down is not None:
            self._down = down
        self._draw()

    def _release(self, e) -> None:
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        self._down = False
        self._draw()
        if inside and self._state != "disabled" and self._command:
            self._command()

    def invoke(self) -> None:
        if self._state != "disabled" and self._command:
            self._command()

    def _draw(self) -> None:
        self.delete("all")
        fill, hover, pressed, ink, dfill, dink = self.KINDS.get(self._kind, self.KINDS["secondary"])
        if self._state == "disabled":
            fill, ink = dfill, dink
        elif self._down:
            fill = pressed
        elif self._hover:
            fill = hover
        w, h = self._width(), self._h
        r = self._radius if self._radius is not None else (8 if self._kind == "icon" else h // 2)
        if fill:
            draw_pill(self, 0, 0, w, h, r, fill, self._bg)
        self.create_text(w / 2, h / 2, text=self._text, fill=ink, font=self._font)

    def configure(self, cnf=None, **kw):  # noqa: D401 - tk-style
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
        elif isinstance(cnf, str):
            return self.cget(cnf)
        redraw = False
        if "text" in kw:
            self._text = kw.pop("text")
            redraw = True
        if "state" in kw:
            self._state = str(kw.pop("state"))
            kw["cursor"] = "arrow" if self._state == "disabled" else "hand2"
            redraw = True
        if "command" in kw:
            self._command = kw.pop("command")
        if "kind" in kw:
            self._kind = kw.pop("kind")
            redraw = True
        if redraw:
            kw.setdefault("width", self._width())
        out = super().configure(**kw) if kw else None
        if redraw:
            self._draw()
        return out

    config = configure

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "state":
            return self._state
        return super().cget(key)

    __getitem__ = cget


class Segmented(tk.Canvas):
    """Segmented control (pill track, accent thumb). Bind to a StringVar and/or get a command(value) callback."""

    def __init__(self, parent: tk.Misc, options: Sequence[tuple[str, str]], variable: tk.StringVar | None = None,
                 command: Callable[[str], None] | None = None, width: int | None = None, height: int = 30,
                 font=None, bg: str | None = None):
        self._bg = bg or _bg_of(parent)
        self._opts = list(options)
        self._var = variable
        self._command = command
        self._font = font or fonts(parent).small_bold
        self._h = height
        self._value = variable.get() if variable else (self._opts[0][0] if self._opts else "")
        self._hover: int | None = None
        natural = sum(measure(parent, self._font, lbl) + 28 for _, lbl in self._opts) + 6
        self._seg_w = max(width or 0, natural)
        super().__init__(parent, width=self._seg_w, height=height, bg=self._bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=0)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda _e: self._hover_to(None))
        self.bind("<ButtonRelease-1>", self._click)
        self.bind("<Configure>", lambda e: self._resize(e.width))
        if variable is not None:
            variable.trace_add("write", lambda *_a: self.set(variable.get(), notify=False))
        self._draw()

    def _resize(self, w: int) -> None:
        if w > 1 and w != self._seg_w:
            self._seg_w = w
            self._draw()

    def _seg_bounds(self) -> list[tuple[float, float]]:
        n = max(1, len(self._opts))
        inner = self._seg_w - 6
        return [(3 + inner * i / n, 3 + inner * (i + 1) / n) for i in range(n)]

    def _index_at(self, x: float) -> int | None:
        for i, (a, b) in enumerate(self._seg_bounds()):
            if a <= x < b:
                return i
        return None

    def _motion(self, e) -> None:
        self._hover_to(self._index_at(e.x))

    def _hover_to(self, i: int | None) -> None:
        if i != self._hover:
            self._hover = i
            self._draw()

    def _click(self, e) -> None:
        i = self._index_at(e.x)
        if i is not None:
            self.set(self._opts[i][0])

    def get(self) -> str:
        return self._value

    def set(self, value: str, notify: bool = True) -> None:
        changed = value != self._value
        self._value = value
        self._draw()
        if notify:
            if self._var is not None and self._var.get() != value:
                self._var.set(value)
            if self._command and changed:
                self._command(value)
            elif self._command and not changed:
                self._command(value)

    def _draw(self) -> None:
        self.delete("all")
        w, h = int(self._seg_w), self._h
        draw_pill(self, 0, 0, w, h, h // 2, SURFACE, self._bg)
        for i, ((val, lbl), (a, b)) in enumerate(zip(self._opts, self._seg_bounds(), strict=False)):
            on = val == self._value
            if on:
                draw_pill(self, int(a), 3, int(b), h - 3, (h - 6) // 2, ACCENT, SURFACE)
            elif i == self._hover:
                draw_pill(self, int(a), 3, int(b), h - 3, (h - 6) // 2, SURFACE_HI, SURFACE)
            ink = ACCENT_INK if on else (INK if i == self._hover else MUTED)
            self.create_text((a + b) / 2, h / 2, text=lbl, fill=ink, font=self._font)


class Toggle(tk.Frame):
    """A switch with a label (and optional muted hint underneath), bound to a BooleanVar."""

    def __init__(self, parent: tk.Misc, variable: tk.BooleanVar, text: str, hint: str = "",
                 command: Callable[[bool], None] | None = None, bg: str | None = None):
        bg = bg or _bg_of(parent)
        super().__init__(parent, bg=bg)
        f = fonts(self)
        self.var = variable
        self._command = command
        self._bg = bg
        self.switch = tk.Canvas(self, width=38, height=22, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.switch.pack(side="right", padx=(12, 0), anchor="n", pady=(1, 0))
        txt = tk.Frame(self, bg=bg)
        txt.pack(side="left", fill="x", expand=True)
        self.label = tk.Label(txt, text=text, bg=bg, fg=INK, font=f.body, anchor="w", justify="left",
                              cursor="hand2")
        self.label.pack(fill="x")
        self.hint = None
        if hint:
            self.hint = tk.Label(txt, text=hint, bg=bg, fg=SUBTLE, font=f.tiny, anchor="w", justify="left")
            self.hint.pack(fill="x")
        for wdg in (self.switch, self.label):
            wdg.bind("<Button-1>", lambda _e: self.toggle())
        variable.trace_add("write", lambda *_a: self._draw())
        self._draw()

    def toggle(self) -> None:
        self.var.set(not self.var.get())
        if self._command:
            self._command(self.var.get())

    def _draw(self) -> None:
        c = self.switch
        c.delete("all")
        on = bool(self.var.get())
        draw_pill(c, 0, 0, 38, 22, 11, ACCENT if on else SURFACE_HI, self._bg,
                  outline=None if on else BORDER_HI)
        kx = 27 if on else 11
        draw_pill(c, kx - 8, 3, kx + 8, 19, 8, "#ffffff" if on else MUTED, ACCENT if on else SURFACE_HI)


class Field(tk.Frame):
    """Flat text input with padding, a focus ring, an optional placeholder and an optional show/hide eye.

    `.entry` is the real tk.Entry (so .get/.insert/.delete/.bind work as usual); placeholder text is drawn as
    an overlay and never ends up in .get().
    """

    def __init__(self, parent: tk.Misc, variable: tk.StringVar | None = None, placeholder: str = "",
                 show: str = "", eye: bool = False, font=None, bg: str | None = None, width: int = 20):
        outer_bg = bg or _bg_of(parent)
        super().__init__(parent, bg=FIELD, highlightthickness=1, highlightbackground=BORDER,
                         highlightcolor=BORDER, bd=0)
        self._outer_bg = outer_bg
        f = fonts(self)
        self.var = variable or tk.StringVar(self)
        self._show = show
        self.entry = tk.Entry(self, textvariable=self.var, bg=FIELD, fg=INK, insertbackground=INK,
                              disabledbackground=SURFACE, readonlybackground=FIELD, selectbackground=ACCENT_LO,
                              selectforeground=INK, relief="flat", bd=0, highlightthickness=0,
                              font=font or f.body, show=show, width=width)
        self.trailing = tk.Frame(self, bg=FIELD)
        self.trailing.pack(side="right", fill="y", padx=(0, 4))
        self.entry.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=7)
        self.eye = None
        if eye:
            self.eye = PillButton(self.trailing, "👁", self._toggle_show, kind="icon", height=24, bg=FIELD,
                                  font=(f.family, 10))
            self.eye.pack(side="right", pady=3)
        self.placeholder = None
        if placeholder:
            self.placeholder = tk.Label(self, text=placeholder, bg=FIELD, fg=SUBTLE, font=font or f.body,
                                        anchor="w", cursor="xterm")
            self.placeholder.bind("<Button-1>", lambda _e: self.entry.focus_set())
            self.var.trace_add("write", lambda *_a: self._sync_placeholder())
            self.after_idle(self._sync_placeholder)
        self.entry.bind("<FocusIn>", lambda _e: self.config(highlightbackground=ACCENT, highlightcolor=ACCENT),
                        add="+")
        self.entry.bind("<FocusOut>", lambda _e: self.config(highlightbackground=BORDER, highlightcolor=BORDER),
                        add="+")

    def set_placeholder(self, text: str) -> None:
        if self.placeholder is not None:
            self.placeholder.config(text=text)

    def _sync_placeholder(self) -> None:
        if self.placeholder is None:
            return
        try:
            if self.var.get():
                self.placeholder.place_forget()
            else:
                self.placeholder.place(in_=self.entry, x=0, rely=0.5, anchor="w")
        except tk.TclError:
            pass

    def _toggle_show(self) -> None:
        cur = self.entry.cget("show")
        self.entry.config(show="" if cur else (self._show or "•"))
        if self.eye is not None:
            self.eye.config(text="🙈" if cur else "👁")

    def get(self) -> str:
        return self.entry.get()


class Card(tk.Frame):
    """A grouped section: surface-coloured block with a bold title, an optional subtitle, and `.body`."""

    def __init__(self, parent: tk.Misc, title: str = "", subtitle: str = "", padding: int = 16,
                 bg: str = CARD):
        super().__init__(parent, bg=bg, highlightthickness=1, highlightbackground="#272830", bd=0)
        f = fonts(self)
        if title:
            section_header(self, title, subtitle, bg=bg).pack(fill="x", padx=padding, pady=(padding - 2, 0))
        self.body = tk.Frame(self, bg=bg)
        self.body.pack(fill="both", expand=True, padx=padding, pady=(10 if title else padding, padding))
        self._font = f


def section_header(parent: tk.Misc, title: str, subtitle: str = "", bg: str | None = None) -> tk.Frame:
    """Bold title + muted one-line subtitle, as a frame you can pack/grid."""
    bg = bg or _bg_of(parent)
    f = fonts(parent)
    fr = tk.Frame(parent, bg=bg)
    tk.Label(fr, text=title, bg=bg, fg=INK, font=f.title, anchor="w").pack(fill="x")
    if subtitle:
        tk.Label(fr, text=subtitle, bg=bg, fg=SUBTLE, font=f.tiny, anchor="w", justify="left").pack(fill="x")
    return fr


def form_row(parent: tk.Misc, label: str, widget_factory: Callable[[tk.Frame], tk.Widget], hint: str = "",
             bg: str | None = None, pady: tuple[int, int] = (0, 10)) -> tk.Widget:
    """Label above a full-width control, with an optional muted hint below. Returns the control."""
    bg = bg or _bg_of(parent)
    f = fonts(parent)
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", pady=pady)
    tk.Label(row, text=label, bg=bg, fg=MUTED, font=f.small_bold, anchor="w").pack(fill="x", pady=(0, 4))
    w = widget_factory(row)
    w.pack(fill="x")
    if hint:
        tk.Label(row, text=hint, bg=bg, fg=SUBTLE, font=f.tiny, anchor="w", justify="left",
                 wraplength=440).pack(fill="x",
                                                                                              pady=(3, 0))
    return w


def divider(parent: tk.Misc, color: str = BORDER, pady: int = 8) -> tk.Frame:
    d = tk.Frame(parent, bg=color, height=1)
    d.pack(fill="x", pady=pady)
    return d


def style_text(text: tk.Text, bg: str = CARD, fg: str = INK) -> tk.Text:
    """Dark, flat text area with tags: code (dark panel), codepad (panel padding line), icode (inline code), b."""
    f = fonts(text)
    text.configure(bg=bg, fg=fg, font=f.body, relief="flat", bd=0, highlightthickness=0, insertbackground=fg,
                   selectbackground=ACCENT_LO, selectforeground=INK, padx=0, pady=0, spacing1=1, spacing2=3,
                   spacing3=5)
    panel = {"background": CODE_BG}
    text.tag_configure("code", font=f.mono, foreground=CODE_INK, lmargin1=12, lmargin2=12, rmargin=12,
                       spacing1=0, spacing2=1, spacing3=0, wrap="char", **panel)
    text.tag_configure("codepad", font=(f.mono_family, 4), spacing1=0, spacing2=0, spacing3=0, **panel)
    try:  # Tk >= 8.6.6: paint the margins too so the panel is a solid block
        text.tag_configure("code", lmargincolor=CODE_BG, rmargincolor=CODE_BG)
        text.tag_configure("codepad", lmargincolor=CODE_BG, rmargincolor=CODE_BG)
    except tk.TclError:
        pass
    text.tag_configure("icode", font=f.mono, foreground=ICODE_INK, background=ICODE_BG)
    text.tag_configure("b", font=f.bold)
    return text


class ScrollFrame(tk.Frame):
    """A vertically scrolling container; put children in `.body`.

    The scrollbar is always there (so it can't get squeezed out), and the mouse wheel works anywhere in
    the window - the binding sits on the toplevel, which every child widget's events pass through.
    """

    def __init__(self, parent: tk.Misc, bg: str | None = None, max_height: int | None = None):
        bg = bg or _bg_of(parent)
        super().__init__(parent, bg=bg)
        self._max_h = max_height
        self.bar = ttk.Scrollbar(self, orient="vertical", style="MC.Vertical.TScrollbar")
        self.bar.pack(side="right", fill="y", padx=(6, 0))  # packed first: always gets its space
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, yscrollincrement=24)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.configure(command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.body = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.bind_all_wheel()

    def _on_body(self, _e=None) -> None:
        bw, bh = self.body.winfo_reqwidth(), self.body.winfo_reqheight()
        self.canvas.configure(scrollregion=(0, 0, bw, bh), width=bw,
                              height=min(bh, self._max_h) if self._max_h else bh)

    def can_scroll(self) -> bool:
        return self.body.winfo_reqheight() > max(1, self.canvas.winfo_height())

    def scroll_to(self, widget: tk.Misc) -> None:
        """Scroll so `widget` (anything inside .body) is at the top."""
        self.update_idletasks()
        y = widget.winfo_rooty() - self.body.winfo_rooty()
        total = max(1, self.body.winfo_reqheight())
        self.canvas.yview_moveto(max(0.0, min(1.0, y / total)))

    def bind_all_wheel(self) -> None:
        def wheel(e):
            if not self.winfo_exists() or not self.can_scroll():
                return None
            if str(e.widget).endswith("popdown.f.l") or e.widget.winfo_class() == "TCombobox":
                return None  # let dropdowns use the wheel themselves
            if getattr(e, "num", 0) in (4, 5):
                step = -1 if e.num == 4 else 1
            else:
                d = getattr(e, "delta", 0)
                step = -max(1, abs(d) // 120) if d > 0 else max(1, abs(d) // 120)
            self.canvas.yview_scroll(step * 2, "units")
            return "break"

        top = self.winfo_toplevel()
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            top.bind(seq, wheel, add="+")
