import ctypes
import tkinter as tk
from functools import lru_cache
from tkinter import font as tkfont
from typing import Callable
from PIL import Image, ImageDraw, ImageTk

from shiny.app.ui.screen import app_in_foreground, place_in_monitor, work_area
from shiny.app.ui.theme import FONT, FONT_BOLD, FONT_SMALL, P, dp

SUPERSAMPLE = 4


@lru_cache(maxsize=1024)
def rounded(width: int, height: int, radius: int, fill: str, outline: str = "", border: int = 1) -> ImageTk.PhotoImage:
    width, height = max(width, 1), max(height, 1)
    s = SUPERSAMPLE
    image = Image.new("RGBA", (width * s, height * s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    r = min(radius * s, min(width, height) * s // 2)
    if outline and min(width, height) <= 2 * border + 1:
        outline = ""
    if outline:
        draw.rounded_rectangle((0, 0, width * s - 1, height * s - 1), r, fill=outline)
        inset = border * s
        draw.rounded_rectangle((inset, inset, width * s - 1 - inset, height * s - 1 - inset), max(r - inset, 0), fill=fill)
    elif fill:
        draw.rounded_rectangle((0, 0, width * s - 1, height * s - 1), r, fill=fill)
    return ImageTk.PhotoImage(image.resize((width, height), Image.LANCZOS))


def background_of(widget: tk.Misc) -> str:
    try:
        return widget.cget("background")
    except tk.TclError:
        return P.panel


class RoundedFrame(tk.Canvas):

    def __init__(self, parent: tk.Misc, radius: int = 12, fill: str = P.card, outline: str = P.border, pad: int = 14, bg: str | None = None,
                 stretch: bool = False):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0, height=dp(160) if stretch else 1)
        self._radius, self._fill, self._outline, self._pad, self._stretch = dp(radius), fill, outline, dp(pad), stretch
        self.body = tk.Frame(self, background=fill)
        self._image_item = self.create_image(0, 0, anchor="nw")
        self._window_item = self.create_window(self._pad, self._pad, window=self.body, anchor="nw")
        self.bind("<Configure>", self._resized)
        self.body.bind("<Configure>", self._body_resized)
        self._size = (0, 0)
        self.after_idle(self._fit)

    def _resized(self, event) -> None:
        if (event.width, event.height) != self._size:
            self._size = (event.width, event.height)
            self.itemconfigure(self._image_item, image=rounded(event.width, event.height, self._radius, self._fill, self._outline, max(1, dp(1))))
            self.itemconfigure(self._window_item, width=max(event.width - 2 * self._pad, 1))
            if self._stretch:
                self.itemconfigure(self._window_item, height=max(event.height - 2 * self._pad, 1))

    def _body_resized(self, _event=None) -> None:
        self._fit()

    def _fit(self) -> None:
        if self._stretch:
            return
        wanted = self.body.winfo_reqheight() + 2 * self._pad
        if int(self.cget("height")) != wanted:
            self.configure(height=wanted)
        self.after_idle(self._fit_later)

    def _fit_later(self) -> None:
        try:
            wanted = self.body.winfo_reqheight() + 2 * self._pad
            if int(self.cget("height")) != wanted:
                self.configure(height=wanted)
        except tk.TclError:
            pass


class Button(tk.Canvas):

    KINDS = {
        "primary": dict(fill=P.accent, hover=P.accent_hover, press=P.accent_press, text="#ffffff", outline=""),
        "secondary": dict(fill=P.button, hover=P.button_hover, press=P.button_press, text=P.text, outline=P.border),
        "danger": dict(fill=P.danger_dim, hover=P.danger_hover, press=P.danger_press, text=P.danger, outline=""),
        "ghost": dict(fill="", hover=P.button, press=P.button_hover, text=P.muted, outline=""),
    }

    def __init__(self, parent: tk.Misc, text: str, command: Callable[[], None] | None = None, kind: str = "secondary", padx: int = 16, pady: int = 8,
                 font=FONT_BOLD, radius: int = 9, bg: str | None = None):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0, takefocus=0, cursor="hand2")
        self._text, self._command, self._kind, self._font = text, command, kind, font
        self._padx, self._pady, self._radius = dp(padx), dp(pady), dp(radius)
        self._hover = self._pressed = False
        self._disabled = False
        self._size = (0, 0)
        self._measure()
        self.bind("<Configure>", self._configured)
        self.bind("<Enter>", lambda _e: self._set(hover=True))
        self.bind("<Leave>", lambda _e: self._set(hover=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda _e: self._set(pressed=True))
        self.bind("<ButtonRelease-1>", self._released)

    def _measure(self) -> None:
        face = tkfont.Font(font=self._font)
        super().configure(width=face.measure(self._text) + 2 * self._padx, height=face.metrics("linespace") + 2 * self._pady)

    def _set(self, hover: bool | None = None, pressed: bool | None = None) -> None:
        if hover is not None:
            self._hover = hover
        if pressed is not None:
            self._pressed = pressed
        self._draw()

    def _released(self, event) -> None:
        was = self._pressed
        self._set(pressed=False)
        if was and not self._disabled and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height() and self._command:
            self._command()

    def _configured(self, event) -> None:
        self._size = (event.width, event.height)
        self._draw()

    def _draw(self) -> None:
        width, height = self._size
        if width < 2:
            return
        style = self.KINDS[self._kind]
        if self._disabled:
            fill, outline, color = (P.card if style["fill"] else ""), "", P.disabled
        elif self._pressed:
            fill, outline, color = style["press"], style["outline"], style["text"]
        elif self._hover:
            fill, outline, color = style["hover"], style["outline"], (style["text"] if self._kind != "ghost" else P.text)
        else:
            fill, outline, color = style["fill"], style["outline"], style["text"]
        self.delete("all")
        if fill:
            self.create_image(0, 0, anchor="nw", image=rounded(width, height, self._radius, fill, outline, max(1, dp(1))))
        self.create_text(width // 2, height // 2, text=self._text, font=self._font, fill=color)
        super().configure(cursor="arrow" if self._disabled else "hand2")

    def configure(self, cnf=None, **options):
        if "text" in options:
            self._text = options.pop("text")
            self._measure()
        if "state" in options:
            self._disabled = options.pop("state") == "disabled"
        if "command" in options:
            self._command = options.pop("command")
        if options or cnf:
            super().configure(cnf, **options)
        self._draw()

    config = configure

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self._disabled else ()
        for item in spec:
            self._disabled = item == "disabled"
        self._draw()


class Segmented(tk.Canvas):

    def __init__(self, parent: tk.Misc, items: list[tuple[object, str]], variable: tk.Variable, command: Callable[[], None] | None = None,
                 tips: dict[object, str] | None = None, bg: str | None = None, font=FONT_SMALL, padx: int = 12, track: str = P.bg, min_width: int = 0):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0, takefocus=0)
        self._items, self._variable, self._command, self._tips = items, variable, command, tips or {}
        self._font, self._track, self._disabled, self._hover = font, track, False, None
        face = tkfont.Font(font=font)
        self._widths = [max(face.measure(label) + 2 * dp(padx), dp(min_width)) for _value, label in items]
        self._gap = dp(2)
        self._inner = dp(3)
        total = sum(self._widths) + self._gap * (len(items) - 1) + 2 * self._inner
        super().configure(width=total, height=face.metrics("linespace") + 2 * dp(7) + 2 * self._inner)
        self._size = (0, 0)
        self._tip_window: tk.Toplevel | None = None
        self._tip_job = None
        self.bind("<Configure>", lambda e: (setattr(self, "_size", (e.width, e.height)), self._draw()))
        self.bind("<Motion>", self._moved)
        self.bind("<Leave>", self._left)
        self.bind("<ButtonPress-1>", self._clicked)
        variable.trace_add("write", lambda *_: self._draw())

    def _index_at(self, x: int) -> int | None:
        left = self._inner
        for index, width in enumerate(self._widths):
            if left <= x < left + width:
                return index
            left += width + self._gap
        return None

    def _moved(self, event) -> None:
        index = self._index_at(event.x)
        if index != self._hover:
            self._hover = index
            self._draw()
            self._hide_tip()
            value = self._items[index][0] if index is not None else None
            if value in self._tips:
                self._tip_job = self.after(450, lambda: self._show_tip(self._tips[value], index))

    def _left(self, _event) -> None:
        self._hover = None
        self._hide_tip()
        self._draw()

    def _show_tip(self, text: str, index: int) -> None:
        self._tip_job = None
        x = self.winfo_rootx() + self._inner + sum(self._widths[:index]) + self._gap * index
        window = tk.Toplevel(self)
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x}+{self.winfo_rooty() + self.winfo_height() + dp(6)}")
        tk.Label(window, text=text, background=P.card, foreground=P.text, font=FONT_SMALL, padx=dp(10), pady=dp(6), borderwidth=1, relief="solid").pack()
        self._tip_window = window

    def _hide_tip(self) -> None:
        if self._tip_job is not None:
            self.after_cancel(self._tip_job)
            self._tip_job = None
        if self._tip_window is not None:
            self._tip_window.destroy()
            self._tip_window = None

    def _clicked(self, event) -> None:
        index = self._index_at(event.x)
        if index is None or self._disabled:
            return
        self._hide_tip()
        self._variable.set(self._items[index][0])
        if self._command:
            self._command()

    def _draw(self) -> None:
        width, height = self._size
        if width < 2:
            return
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=rounded(width, height, dp(10), self._track, P.border, max(1, dp(1))))
        left = self._inner
        current = self._variable.get()
        for index, ((value, label), item_width) in enumerate(zip(self._items, self._widths)):
            selected = value == current
            top, bottom = self._inner, height - self._inner
            if selected:
                self.create_image(left, top, anchor="nw", image=rounded(item_width, bottom - top, dp(8), P.accent_dim if not self._disabled else P.card, ""))
                color = P.accent_text if not self._disabled else P.disabled
            elif index == self._hover and not self._disabled:
                self.create_image(left, top, anchor="nw", image=rounded(item_width, bottom - top, dp(8), P.button, ""))
                color = P.text
            else:
                color = P.muted if not self._disabled else P.disabled
            self.create_text(left + item_width // 2, height // 2, text=label, font=self._font, fill=color)
            left += item_width + self._gap
        super().configure(cursor="arrow" if self._disabled else "hand2")

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self._disabled else ()
        for item in spec:
            self._disabled = item == "disabled"
        self._draw()


class NavList(tk.Canvas):

    def __init__(self, parent: tk.Misc, on_select: Callable[[], None], bg: str | None = None):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0, takefocus=0, height=dp(40))
        self._on_select = on_select
        self._names: list[str] = []
        self._rects: list[tuple[int, int, int, int]] = []
        self._selected: int | None = None
        self._hover: int | None = None
        self._disabled = False
        self._face = tkfont.Font(font=FONT_BOLD)
        self._laid_out_for = -1
        self.bind("<Configure>", lambda _e: self._layout())
        self.bind("<Motion>", self._moved)
        self.bind("<Leave>", lambda _e: self._set_hover(None))
        self.bind("<ButtonPress-1>", self._clicked)

    def set_items(self, names: list[str]) -> None:
        self._names, self._selected, self._hover = list(names), None, None
        self._laid_out_for = -1
        self._layout()

    def _layout(self) -> None:
        width = self.winfo_width()
        if width < 20:
            return
        if width == self._laid_out_for and len(self._rects) == len(self._names):
            return
        self._laid_out_for = width
        gap, pill_h = dp(6), self._face.metrics("linespace") + 2 * dp(8)
        x = y = 0
        self._rects = []
        for name in self._names:
            pill_w = self._face.measure(name) + 2 * dp(16)
            if x and x + pill_w > width:
                x, y = 0, y + pill_h + gap
            self._rects.append((x, y, x + pill_w, y + pill_h))
            x += pill_w + gap
        total = (y + pill_h) if self._rects else dp(40)
        if int(self.cget("height")) != total:
            self.configure(height=total)
        self._draw()

    def _index_at(self, x: int, y: int) -> int | None:
        for index, (left, top, right, bottom) in enumerate(self._rects):
            if left <= x < right and top <= y < bottom:
                return index
        return None

    def _moved(self, event) -> None:
        self._set_hover(self._index_at(event.x, event.y))

    def _set_hover(self, index: int | None) -> None:
        if index != self._hover:
            self._hover = index
            self._draw()

    def _clicked(self, event) -> None:
        index = self._index_at(event.x, event.y)
        if index is None or self._disabled or index == self._selected:
            return
        self._selected = index
        self._draw()
        self._on_select()

    def _draw(self) -> None:
        self.delete("all")
        for index, (left, top, right, bottom) in enumerate(self._rects):
            selected = index == self._selected
            width, height = right - left, bottom - top
            if selected:
                image = rounded(width, height, height // 2, P.accent_dim, P.accent if not self._disabled else P.border, max(1, dp(1)))
                color = P.accent_text if not self._disabled else P.disabled
            elif index == self._hover and not self._disabled:
                image = rounded(width, height, height // 2, P.button, P.border_strong, max(1, dp(1)))
                color = P.text
            else:
                image = rounded(width, height, height // 2, P.card, P.border, max(1, dp(1)))
                color = P.muted if not self._disabled else P.disabled
            self.create_image(left, top, anchor="nw", image=image)
            self.create_text((left + right) // 2, (top + bottom) // 2, text=self._names[index], font=FONT_BOLD, fill=color)
        super().configure(cursor="arrow" if self._disabled else "hand2")

    def curselection(self) -> tuple[int, ...]:
        return () if self._selected is None else (self._selected,)

    def set_disabled(self, disabled: bool) -> None:
        self._disabled = disabled
        self._draw()


class Chip(tk.Canvas):

    def __init__(self, parent: tk.Misc, bg: str | None = None):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0)
        self._text, self._color, self._fill = "", P.muted, P.button
        self._face = tkfont.Font(font=FONT_SMALL)
        super().configure(height=self._face.metrics("linespace") + 2 * dp(4))
        self.bind("<Configure>", lambda _e: self._draw())

    def set(self, text: str, color: str, fill: str) -> None:
        if (text, color, fill) == (self._text, self._color, self._fill):
            return
        self._text, self._color, self._fill = text, color, fill
        super().configure(width=self._face.measure(text) + 2 * dp(10))
        self._draw()

    def _draw(self) -> None:
        width, height = self.winfo_width(), self.winfo_height()
        if width < 2:
            return
        self.delete("all")
        if self._text:
            self.create_image(0, 0, anchor="nw", image=rounded(width, height, height // 2, self._fill, ""))
            self.create_text(width // 2, height // 2, text=self._text, font=FONT_SMALL, fill=self._color)


class Toggle(tk.Canvas):

    def __init__(self, parent: tk.Misc, text: str, variable: tk.BooleanVar, command: Callable[[], None] | None = None, bg: str | None = None):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0, takefocus=0)
        self._text, self._variable, self._command = text, variable, command
        self._disabled = False
        self._track = (dp(38), dp(22))
        self._gap = dp(10)
        face = tkfont.Font(font=FONT)
        super().configure(width=self._track[0] + self._gap + face.measure(text) + dp(2), height=max(self._track[1], face.metrics("linespace")) + dp(4))
        self._size = (0, 0)
        self.bind("<Configure>", lambda e: (setattr(self, "_size", (e.width, e.height)), self._draw()))
        self.bind("<ButtonPress-1>", self._clicked)
        variable.trace_add("write", lambda *_: self._draw())

    def _clicked(self, _event) -> None:
        if self._disabled:
            return
        self._variable.set(not self._variable.get())
        if self._command:
            self._command()

    def _draw(self) -> None:
        width, height = self._size
        if width < 2:
            return
        self.delete("all")
        on = bool(self._variable.get())
        track_w, track_h = self._track
        top = (height - track_h) // 2
        fill = (P.accent if on else P.button_press) if not self._disabled else P.card
        self.create_image(0, top, anchor="nw", image=rounded(track_w, track_h, track_h // 2, fill, "" if on else P.border_strong, max(1, dp(1))))
        knob = track_h - dp(8)
        left = track_w - knob - dp(4) if on else dp(4)
        self.create_image(left, top + dp(4), anchor="nw", image=rounded(knob, knob, knob // 2, "#ffffff" if not self._disabled else P.disabled, ""))
        self.create_text(track_w + self._gap, height // 2, text=self._text, font=FONT, fill=P.text if not self._disabled else P.disabled, anchor="w")
        super().configure(cursor="arrow" if self._disabled else "hand2")

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self._disabled else ()
        for item in spec:
            self._disabled = item == "disabled"
        self._draw()


def round_window(window: tk.Toplevel, border: str = P.border_strong) -> None:
    try:
        window.update_idletasks()
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        handle = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        dwm.DwmSetWindowAttribute(handle, 33, ctypes.byref(ctypes.c_int(2)), 4)
        red, green, blue = int(border[1:3], 16), int(border[3:5], 16), int(border[5:7], 16)
        dwm.DwmSetWindowAttribute(handle, 34, ctypes.byref(ctypes.c_int(blue << 16 | green << 8 | red)), 4)
    except (AttributeError, OSError, tk.TclError):
        pass


class Slider(tk.Canvas):

    def __init__(self, parent: tk.Misc, variable: tk.IntVar, minimum: int = 0, maximum: int = 100, command: Callable[[int], None] | None = None,
                 bg: str | None = None, width: int = 180, step: int = 5):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0, takefocus=0, cursor="hand2")
        self._variable, self._min, self._max, self._command, self._step = variable, minimum, maximum, command, step
        self._hover = False
        self._size = (0, 0)
        super().configure(width=dp(width), height=dp(26))
        self.bind("<Configure>", lambda e: (setattr(self, "_size", (e.width, e.height)), self._draw()))
        self.bind("<ButtonPress-1>", self._set_from_mouse)
        self.bind("<B1-Motion>", self._set_from_mouse)
        self.bind("<MouseWheel>", lambda e: self._set(self._variable.get() + (self._step if e.delta > 0 else -self._step)))
        self.bind("<Enter>", lambda _e: self._hovered(True))
        self.bind("<Leave>", lambda _e: self._hovered(False))
        variable.trace_add("write", lambda *_: self._draw())

    def _hovered(self, value: bool) -> None:
        self._hover = value
        self._draw()

    def _set(self, value: int) -> None:
        value = max(self._min, min(self._max, int(value)))
        if value != self._variable.get():
            self._variable.set(value)
            if self._command:
                self._command(value)

    def _set_from_mouse(self, event) -> None:
        width = self._size[0]
        edge = dp(10)
        if width > 2 * edge:
            self._set(self._min + (event.x - edge) / (width - 2 * edge) * (self._max - self._min) + 0.5)

    def _draw(self) -> None:
        width, height = self._size
        if width < 2:
            return
        self.delete("all")
        edge, track = dp(10), dp(6)
        fraction = (self._variable.get() - self._min) / max(1, self._max - self._min)
        left, right = edge, width - edge
        x = left + (right - left) * fraction
        top = (height - track) // 2
        self.create_image(left, top, anchor="nw", image=rounded(right - left, track, track // 2, P.button_press, ""))
        if x - left >= 2:
            self.create_image(left, top, anchor="nw", image=rounded(int(x - left), track, track // 2, P.accent, ""))
        knob = dp(16) + (dp(2) if self._hover else 0)
        self.create_image(int(x - knob / 2), (height - knob) // 2, anchor="nw", image=rounded(knob, knob, knob // 2, "#ffffff", P.accent, max(1, dp(2))))


class SearchSelect(tk.Canvas):

    ROW_PAD = 8
    MAX_ROWS = 9

    def __init__(self, parent: tk.Misc, textvariable: tk.StringVar, values=(), bg: str | None = None, width: int = 220, placeholder: str = "Search…"):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0, takefocus=0, cursor="hand2")
        self._variable = textvariable
        self._values = list(values)
        self._placeholder = placeholder
        self._disabled = False
        self._hover = False
        self._popup: tk.Toplevel | None = None
        self._click_binding = None
        self._face = tkfont.Font(font=FONT)
        self._size = (0, 0)
        super().configure(width=dp(width), height=self._face.metrics("linespace") + 2 * dp(10))
        self.bind("<Configure>", lambda e: (setattr(self, "_size", (e.width, e.height)), self._draw()))
        self.bind("<Enter>", lambda _e: self._hovered(True))
        self.bind("<Leave>", lambda _e: self._hovered(False))
        self.bind("<ButtonPress-1>", self._toggle)
        textvariable.trace_add("write", lambda *_: self._draw())

    def _hovered(self, value: bool) -> None:
        self._hover = value
        self._draw()

    def _draw(self) -> None:
        width, height = self._size
        if width < 2:
            return
        self.delete("all")
        opened = self._popup is not None
        outline = P.accent if opened else (P.border_strong if not self._hover or self._disabled else P.subtle)
        self.create_image(0, 0, anchor="nw", image=rounded(width, height, dp(9), P.bg if not self._disabled else P.card, outline, max(1, dp(1))))
        text = self._variable.get()
        room = width - dp(46)
        while text and self._face.measure(text) > room:
            text = text[:-2] + "…" if not text.endswith("…") else text[:-2] + "…"
            if len(text) < 3:
                break
        self.create_text(dp(14), height // 2, text=text, font=FONT, fill=P.text if not self._disabled else P.disabled, anchor="w")
        cx, cy, half = width - dp(18), height // 2, dp(4)
        color = P.muted if not self._disabled else P.disabled
        sign = -1 if opened else 1
        self.create_line(cx - half, cy - sign * dp(2), cx, cy + sign * dp(2), cx + half, cy - sign * dp(2), fill=color, width=max(1, dp(2)), capstyle="round", joinstyle="round")
        super().configure(cursor="arrow" if self._disabled else "hand2")

    def configure(self, cnf=None, **options):
        if "values" in options:
            self._values = list(options.pop("values"))
        if "state" in options:
            self._disabled = options.pop("state") == "disabled"
        options.pop("textvariable", None)
        if options or cnf:
            super().configure(cnf, **options)
        self._draw()

    config = configure

    def state(self, spec=None):
        if spec is None:
            return ("disabled",) if self._disabled else ()
        for item in spec:
            self._disabled = item == "disabled"
        self._draw()

    def _toggle(self, _event=None) -> None:
        if self._disabled:
            return
        if self._popup is not None:
            self._close()
        else:
            self._open()

    def _open(self) -> None:
        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(background=P.border_strong)
        self._popup = popup
        body = tk.Frame(popup, background=P.card)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        self._query = tk.StringVar()
        width = max(self.winfo_width(), dp(280))
        field = RoundedFrame(body, radius=9, fill=P.bg, outline=P.accent, pad=10, bg=P.card)
        field.configure(width=width - dp(20))
        field.pack(fill="x", padx=dp(10), pady=(dp(10), dp(6)))
        self._entry = tk.Entry(field.body, textvariable=self._query, background=P.bg, foreground=P.text, insertbackground=P.text, relief="flat", borderwidth=0,
                               font=FONT, highlightthickness=0, selectbackground=P.accent_dim, selectforeground="white")
        self._entry.pack(fill="x", pady=dp(2))
        self._hint = tk.Label(field.body, text=self._placeholder, background=P.bg, foreground=P.subtle, font=FONT)
        self._hint.place(x=0, rely=0.5, anchor="w")
        self._hint.bind("<ButtonPress-1>", lambda _e: self._entry.focus_force())

        self._row_height = self._face.metrics("linespace") + 2 * dp(self.ROW_PAD)
        self._rows_visible = min(max(len(self._values), 1), self.MAX_ROWS)
        self._list = tk.Canvas(body, background=P.card, highlightthickness=0, borderwidth=0, width=width - dp(20), height=self._rows_visible * self._row_height)
        self._list.pack(padx=dp(10), pady=(0, dp(10)))
        self._matches = list(self._values)
        self._active = self._matches.index(self._variable.get()) if self._variable.get() in self._matches else 0
        self._offset = 0
        self._ensure_visible()

        x, y = self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + dp(6)
        popup.update_idletasks()
        width_now, height = popup.winfo_reqwidth(), popup.winfo_reqheight()
        _left, _top, _right, bottom = work_area(self.winfo_rootx(), self.winfo_rooty(), (0, 0, self.winfo_screenwidth(), self.winfo_screenheight()))
        if y + height > bottom - dp(8):
            y = max(_top, self.winfo_rooty() - height - dp(6))
        x, y = place_in_monitor(x, y, width_now, height, self.winfo_rootx(), self.winfo_rooty())
        popup.wm_geometry(f"+{x}+{y}")
        round_window(popup)

        self._query.trace_add("write", lambda *_: self._refilter())
        self._list.bind("<Motion>", self._list_moved)
        self._list.bind("<ButtonPress-1>", self._list_clicked)
        self._list.bind("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1))
        for widget in (popup, self._entry):
            widget.bind("<Escape>", lambda _e: (self._close(), "break")[1])
            widget.bind("<Down>", lambda _e: (self._step(1), "break")[1])
            widget.bind("<Up>", lambda _e: (self._step(-1), "break")[1])
            widget.bind("<Return>", lambda _e: (self._choose(self._active), "break")[1])
            widget.bind("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1))
        self._click_binding = self.winfo_toplevel().bind("<ButtonPress-1>", self._outside_click, add="+")
        self._draw()
        self._paint_list()
        popup.after(30, self._entry.focus_force)
        popup.after(120, self._watch_foreground)

    def _watch_foreground(self) -> None:
        if self._popup is None:
            return
        if app_in_foreground():
            self._popup.after(120, self._watch_foreground)
        else:
            self._close()

    def _outside_click(self, event) -> None:
        if self._popup is None:
            return
        try:
            inside = event.widget.winfo_toplevel() is self._popup or event.widget is self
        except (AttributeError, tk.TclError):
            inside = False
        if not inside:
            self._close()

    def _close(self) -> None:
        if self._popup is not None:
            try:
                self.winfo_toplevel().unbind("<ButtonPress-1>", self._click_binding)
            except tk.TclError:
                pass
            self._popup.destroy()
            self._popup = None
            self._draw()

    def _refilter(self) -> None:
        query = self._query.get().strip().lower()
        self._hint.place_forget() if query else self._hint.place(x=0, rely=0.5, anchor="w")
        starts = [value for value in self._values if value.lower().startswith(query)]
        contains = [value for value in self._values if query in value.lower() and value not in starts]
        self._matches = starts + contains if query else list(self._values)
        self._active, self._offset = 0, 0
        self._rows_visible = min(max(len(self._matches), 1), self.MAX_ROWS)
        self._list.configure(height=self._rows_visible * self._row_height)
        self._paint_list()

    def _step(self, direction: int) -> None:
        if self._matches:
            self._active = (self._active + direction) % len(self._matches)
            self._ensure_visible()
            self._paint_list()

    def _ensure_visible(self) -> None:
        if self._active < self._offset:
            self._offset = self._active
        elif self._active >= self._offset + self._rows_visible:
            self._offset = self._active - self._rows_visible + 1
        self._offset = max(0, min(self._offset, max(0, len(self._matches) - self._rows_visible)))

    def _scroll(self, direction: int) -> None:
        self._offset = max(0, min(self._offset + direction * 2, max(0, len(self._matches) - self._rows_visible)))
        self._paint_list()

    def _index_at(self, y: int) -> int | None:
        index = self._offset + y // self._row_height
        return index if 0 <= index < len(self._matches) else None

    def _list_moved(self, event) -> None:
        index = self._index_at(event.y)
        if index is not None and index != self._active:
            self._active = index
            self._paint_list()

    def _list_clicked(self, event) -> None:
        index = self._index_at(event.y)
        if index is not None:
            self._choose(index)

    def _choose(self, index: int) -> None:
        if not 0 <= index < len(self._matches):
            return
        value = self._matches[index]
        self._close()
        self._variable.set(value)
        self.event_generate("<<ComboboxSelected>>")

    def _paint_list(self) -> None:
        canvas = self._list
        canvas.delete("all")
        width, height = int(canvas.cget("width")), int(canvas.cget("height"))
        if not self._matches:
            canvas.create_text(width // 2, height // 2, text="No matches", font=FONT, fill=P.subtle)
            return
        current = self._variable.get()
        for position in range(self._rows_visible):
            index = self._offset + position
            if index >= len(self._matches):
                break
            value = self._matches[index]
            top = position * self._row_height
            chosen = value == current
            if index == self._active:
                canvas.create_image(0, top, anchor="nw", image=rounded(width, self._row_height - dp(2), dp(8), P.accent_dim if chosen else P.button, ""))
            color = P.accent_text if chosen else P.text
            canvas.create_text(dp(12), top + self._row_height // 2, text=value, font=FONT_BOLD if chosen else FONT, fill=color, anchor="w")
            if chosen:
                canvas.create_text(width - dp(14), top + self._row_height // 2, text="✓", font=FONT_BOLD, fill=P.accent, anchor="e")
        if len(self._matches) > self._rows_visible:
            thumb = max(dp(24), height * self._rows_visible // len(self._matches))
            y = (height - thumb) * self._offset // max(1, len(self._matches) - self._rows_visible)
            canvas.create_image(width - dp(5), y, anchor="nw", image=rounded(dp(4), thumb, dp(2), P.border_strong, ""))


class Toast(tk.Canvas):

    LEVELS = {
        "info": (P.card, P.text, P.border_strong),
        "success": (P.success_dim, P.success, P.success_dim),
        "warning": (P.warning_dim, P.warning, P.warning_dim),
        "error": (P.danger_dim, P.danger, P.danger_dim),
    }

    def __init__(self, parent: tk.Misc, wraplength: int = 760):
        super().__init__(parent, background=P.bg, highlightthickness=0, borderwidth=0)
        self._wrap = dp(wraplength)
        self._job = None

    def show(self, text: str, level: str = "info", milliseconds: int = 3500) -> None:
        if not text:
            self.hide()
            return
        fill, color, outline = self.LEVELS.get(level, self.LEVELS["info"])
        self.delete("all")
        item = self.create_text(0, 0, text=text, font=FONT, fill=color, width=self._wrap, anchor="nw")
        left, top, right, bottom = self.bbox(item)
        padx, pady = dp(16), dp(10)
        width, height = right - left + 2 * padx, bottom - top + 2 * pady
        self.delete("all")
        super().configure(width=width, height=height, background=self.master.cget("background"))
        self.create_image(0, 0, anchor="nw", image=rounded(width, height, dp(12), fill, outline, max(1, dp(1))))
        self.create_text(padx, pady, text=text, font=FONT, fill=color, width=self._wrap, anchor="nw")
        self.place(relx=0.5, rely=1.0, y=-dp(22), anchor="s")
        tk.Misc.lift(self)
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(milliseconds if level in ("info", "success") else milliseconds + 3000, self.hide)

    def hide(self) -> None:
        self._job = None
        self.place_forget()


def dark_title_bar(window: tk.Misc) -> None:
    try:
        window.update_idletasks()
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        handle = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        for attribute in (20, 19):
            dwm.DwmSetWindowAttribute(handle, attribute, ctypes.byref(ctypes.c_int(1)), 4)
    except (AttributeError, OSError, tk.TclError):
        pass


class SlimScrollbar(tk.Canvas):

    def __init__(self, parent: tk.Misc, command: Callable | None = None, bg: str | None = None):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0, width=dp(14), takefocus=0)
        self._command = command
        self._first, self._last = 0.0, 1.0
        self._hover = False
        self._drag_offset: float | None = None
        self._size = (0, 0)
        self.bind("<Configure>", lambda e: (setattr(self, "_size", (e.width, e.height)), self._draw()))
        self.bind("<Enter>", lambda _e: self._pointed(True))
        self.bind("<Leave>", lambda _e: self._pointed(False))
        self.bind("<ButtonPress-1>", self._pressed)
        self.bind("<B1-Motion>", self._dragged)
        self.bind("<ButtonRelease-1>", self._released)

    def configure(self, cnf=None, **options):
        if "command" in options:
            self._command = options.pop("command")
        if options or cnf:
            super().configure(cnf, **options)

    config = configure

    def set(self, first, last) -> None:
        self._first, self._last = float(first), float(last)
        self._draw()

    def _pointed(self, value: bool) -> None:
        self._hover = value
        self._draw()

    def _thumb(self) -> tuple[int, int] | None:
        height = self._size[1]
        if height < 2 or self._last - self._first >= 0.999:
            return None
        top = int(self._first * height)
        bottom = max(int(self._last * height), top + dp(32))
        if bottom > height:
            bottom, top = height, height - max(bottom - top, dp(32))
        return max(top, 0), bottom

    def _draw(self) -> None:
        self.delete("all")
        thumb = self._thumb()
        if thumb is None:
            return
        width = self._size[0]
        thick = dp(8) if (self._hover or self._drag_offset is not None) else dp(5)
        color = P.muted if self._drag_offset is not None else (P.subtle if self._hover else P.border_strong)
        top, bottom = thumb
        self.create_image((width - thick) // 2, top, anchor="nw", image=rounded(thick, bottom - top, thick // 2, color, ""))

    def _pressed(self, event) -> None:
        thumb = self._thumb()
        if thumb is None or self._command is None:
            return
        if thumb[0] <= event.y <= thumb[1]:
            self._drag_offset = event.y - thumb[0]
            self._draw()
        else:
            self._command("scroll", -1 if event.y < thumb[0] else 1, "pages")

    def _dragged(self, event) -> None:
        if self._drag_offset is None or self._command is None or self._size[1] < 2:
            return
        self._command("moveto", max(0.0, (event.y - self._drag_offset) / self._size[1]))

    def _released(self, _event) -> None:
        self._drag_offset = None
        self._draw()


def add_window_buttons(window: tk.Misc) -> None:
    try:
        window.update_idletasks()
        user32 = ctypes.windll.user32
        handle = user32.GetParent(window.winfo_id()) or window.winfo_id()
        get, set_ = user32.GetWindowLongW, user32.SetWindowLongW
        get.argtypes, get.restype = [ctypes.c_void_p, ctypes.c_int], ctypes.c_long
        set_.argtypes, set_.restype = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long], ctypes.c_long
        style = get(handle, -16)
        set_(handle, -16, style | 0x20000 | 0x10000 | 0x40000)
        extended = get(handle, -20)
        set_(handle, -20, extended & ~0x1)
        user32.SetWindowPos(handle, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
    except (AttributeError, OSError, tk.TclError):
        pass


class ProgressBar(tk.Canvas):

    def __init__(self, parent: tk.Misc, bg: str | None = None):
        super().__init__(parent, background=bg or background_of(parent), highlightthickness=0, borderwidth=0, height=dp(8))
        self._mode = "determinate"
        self._value = 0.0
        self._phase = 0.0
        self._job = None
        self._size = (0, 0)
        self.bind("<Configure>", lambda e: (setattr(self, "_size", (e.width, e.height)), self._draw()))

    def configure(self, cnf=None, **options):
        if "mode" in options:
            self._mode = options.pop("mode")
        if "value" in options:
            self._value = float(options.pop("value"))
        if options or cnf:
            super().configure(cnf, **options)
        self._draw()

    config = configure

    def start(self, interval: int = 14) -> None:
        self.stop()
        self._tick(interval)

    def _tick(self, interval: int) -> None:
        self._phase = (self._phase + 0.012) % 2.0
        self._draw()
        self._job = self.after(max(10, interval), lambda: self._tick(interval))

    def stop(self) -> None:
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def destroy(self) -> None:
        self.stop()
        super().destroy()

    def _draw(self) -> None:
        width, height = self._size
        if width < 4:
            return
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=rounded(width, height, height // 2, P.button, ""))
        if self._mode == "indeterminate":
            span = width * 0.32
            position = self._phase if self._phase <= 1.0 else 2.0 - self._phase
            left = int((width - span) * position)
            self.create_image(left, 0, anchor="nw", image=rounded(int(span), height, height // 2, P.accent, ""))
        else:
            filled = int(width * max(0.0, min(100.0, self._value)) / 100)
            if filled >= 4:
                self.create_image(0, 0, anchor="nw", image=rounded(filled, height, height // 2, P.accent, ""))
