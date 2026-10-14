import tkinter as tk
from dataclasses import dataclass
from typing import Callable

from shiny.app.ui.theme import FONT, FONT_SMALL, P

ROW_PADDING = 6
SUBMENU_DELAY_MS = 220


@dataclass
class _Entry:
    kind: str
    label: str = ""
    command: Callable[[], None] | None = None
    accelerator: str = ""
    variable: tk.Variable | None = None
    value: object = None
    submenu: "DarkMenu | None" = None
    state: str = "normal"


class DarkMenu:
    open_chain: list["DarkMenu"] = []
    _global_click_bound = False

    def __init__(self, master: tk.Misc, postcommand: Callable[[], None] | None = None):
        self.master = master
        self.postcommand = postcommand
        self.entries: list[_Entry] = []
        self._window: tk.Toplevel | None = None
        self._rows: list[tk.Frame] = []
        self._selected = -1
        self._hovered = -1
        self._submenu_job = None
        self._on_close: Callable[[], None] | None = None


    def add_command(self, label: str, command=None, accelerator: str = "", state: str = "normal") -> None:
        self.entries.append(_Entry("command", label, command, accelerator, state=state))

    def add_checkbutton(self, label: str, variable: tk.Variable, command=None, accelerator: str = "") -> None:
        self.entries.append(_Entry("check", label, command, accelerator, variable=variable))

    def add_radiobutton(self, label: str, variable: tk.Variable, value, command=None, accelerator: str = "") -> None:
        self.entries.append(_Entry("radio", label, command, accelerator, variable=variable, value=value))

    def add_cascade(self, label: str, menu: "DarkMenu") -> None:
        self.entries.append(_Entry("cascade", label, submenu=menu))

    def add_separator(self) -> None:
        self.entries.append(_Entry("separator"))

    def delete(self, first, last=None) -> None:
        if first == 0 and last == "end":
            self.entries.clear()
        else:
            del self.entries[int(first) : int(last if last is not None else first) + 1]

    def entryconfigure(self, index: int, **options) -> None:
        for name, value in options.items():
            setattr(self.entries[index], name.lstrip("-"), value)


    @property
    def is_open(self) -> bool:
        return self._window is not None

    def popup(self, x: int, y: int, on_close: Callable[[], None] | None = None) -> None:
        DarkMenu.close_all()
        self._on_close = on_close
        self._show(x, y)
        self._window.focus_force()

    @classmethod
    def close_all(cls) -> None:
        for menu in list(cls.open_chain):
            menu._hide()

    def close(self) -> None:
        position = DarkMenu.open_chain.index(self) if self in DarkMenu.open_chain else None
        if position is not None:
            for menu in list(DarkMenu.open_chain[position:]):
                menu._hide()

    def _show(self, x: int, y: int) -> None:
        if self.postcommand is not None:
            self.postcommand()
        window = tk.Toplevel(self.master)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(background=P.border)
        body = tk.Frame(window, background=P.card)
        body.pack(padx=1, pady=1)
        self._window = window
        self._rows = []
        self._selected = -1
        self._hovered = -1

        for index, entry in enumerate(self.entries):
            if entry.kind == "separator":
                tk.Frame(body, background=P.border, height=1).pack(fill="x", padx=8, pady=4)
                self._rows.append(None)
                continue
            self._rows.append(self._make_row(body, index, entry))

        window.update_idletasks()
        width, height = window.winfo_reqwidth(), window.winfo_reqheight()
        x = max(0, min(x, window.winfo_screenwidth() - width))
        y = max(0, min(y, window.winfo_screenheight() - height))
        window.geometry(f"+{x}+{y}")

        window.bind("<Escape>", lambda _event: (DarkMenu.close_all(), "break")[1])
        window.bind("<Down>", lambda _event: self._move(1))
        window.bind("<Up>", lambda _event: self._move(-1))
        window.bind("<Return>", lambda _event: self._activate(self._selected))
        window.bind("<Right>", lambda _event: self._open_submenu(self._selected, with_keyboard=True))
        window.bind("<Left>", lambda _event: self._left())
        if not DarkMenu.open_chain:
            window.bind("<FocusOut>", lambda _event: window.after(80, DarkMenu._close_if_app_unfocused))
        DarkMenu.open_chain.append(self)
        DarkMenu._bind_global_click(self.master)

    def _make_row(self, body: tk.Frame, index: int, entry: _Entry) -> tk.Frame:
        disabled = entry.state == "disabled"
        row = tk.Frame(body, background=P.card)
        row.pack(fill="x")
        color = P.disabled if disabled else P.text

        mark = ""
        if entry.kind == "check" and entry.variable.get():
            mark = "✓"
        elif entry.kind == "radio" and entry.variable.get() == entry.value:
            mark = "●"
        widgets = [
            tk.Label(row, text=mark, width=2, background=P.card, foreground=P.accent, font=FONT, anchor="center"),
            tk.Label(row, text=entry.label, background=P.card, foreground=color, font=FONT, anchor="w"),
            tk.Label(
                row,
                text="▸" if entry.kind == "cascade" else entry.accelerator,
                background=P.card,
                foreground=P.muted if not disabled else P.disabled,
                font=FONT_SMALL,
                anchor="e",
            ),
        ]
        widgets[0].pack(side="left", padx=(6, 0), pady=ROW_PADDING)
        widgets[1].pack(side="left", fill="x", expand=True, padx=(2, 18), pady=ROW_PADDING)
        widgets[2].pack(side="right", padx=(0, 12), pady=ROW_PADDING)
        for widget in (row, *widgets):
            widget.bind("<Enter>", lambda _event, index=index: self._hover(index))
            widget.bind("<ButtonRelease-1>", lambda _event, index=index: self._activate(index, by_mouse=True))
        return row

    def _hide(self) -> None:
        if self._submenu_job is not None:
            self._window.after_cancel(self._submenu_job)
            self._submenu_job = None
        if self in DarkMenu.open_chain:
            DarkMenu.open_chain.remove(self)
        if self._window is not None:
            self._window.destroy()
            self._window = None
            self._rows = []
        if self._on_close is not None and not DarkMenu.open_chain:
            callback, self._on_close = self._on_close, None
            callback()


    def _select(self, index: int) -> None:
        if self._selected == index:
            return
        for position, row in enumerate(self._rows):
            if row is None:
                continue
            active = position == index and self.entries[position].state != "disabled"
            background = P.accent_dim if active else P.card
            for widget in (row, *row.winfo_children()):
                widget.configure(background=background)
            if active and self.entries[position].kind != "check":
                row.winfo_children()[1].configure(foreground="white")
            elif not active:
                disabled = self.entries[position].state == "disabled"
                row.winfo_children()[1].configure(foreground=P.disabled if disabled else P.text)
        self._selected = index

    def _hover(self, index: int) -> None:
        if index == self._hovered:
            return
        self._hovered = index
        self._select(index)
        self._close_submenus()
        if self._submenu_job is not None:
            self._window.after_cancel(self._submenu_job)
            self._submenu_job = None
        if self.entries[index].kind == "cascade":
            self._submenu_job = self._window.after(SUBMENU_DELAY_MS, lambda: self._open_submenu(index))

    def _close_submenus(self) -> None:
        position = DarkMenu.open_chain.index(self)
        for menu in list(DarkMenu.open_chain[position + 1 :]):
            menu._hide()

    def _open_submenu(self, index: int, with_keyboard: bool = False) -> None:
        self._submenu_job = None
        if self._window is None or not 0 <= index < len(self.entries) or self.entries[index].kind != "cascade":
            return
        submenu = self.entries[index].submenu
        if submenu.is_open:
            return
        self._close_submenus()
        row = self._rows[index]
        x = self._window.winfo_rootx() + self._window.winfo_width() - 2
        y = row.winfo_rooty() - 4
        submenu._on_close = None
        submenu._show(x, y)
        if with_keyboard:
            submenu._window.focus_force()
            submenu._move(1)

    def _activate(self, index: int, by_mouse: bool = False) -> None:
        if not 0 <= index < len(self.entries):
            return
        entry = self.entries[index]
        if entry.state == "disabled" or entry.kind == "separator":
            return
        if entry.kind == "cascade":
            self._open_submenu(index, with_keyboard=not by_mouse)
            return
        master = self.master
        DarkMenu.close_all()
        master.after(10, lambda: self._invoke_entry(entry))

    @staticmethod
    def _invoke_entry(entry: _Entry) -> None:
        if entry.kind == "check":
            entry.variable.set(not entry.variable.get())
        elif entry.kind == "radio":
            entry.variable.set(entry.value)
        if entry.command is not None:
            entry.command()


    def _move(self, step: int) -> str:
        selectable = [i for i, entry in enumerate(self.entries) if entry.kind != "separator" and entry.state != "disabled"]
        if not selectable:
            return "break"
        if self._selected in selectable:
            target = selectable[(selectable.index(self._selected) + step) % len(selectable)]
        else:
            target = selectable[0] if step > 0 else selectable[-1]
        self._close_submenus()
        self._select(target)
        return "break"

    def _left(self) -> str:
        position = DarkMenu.open_chain.index(self)
        if position == 0:
            return "break"
        self._hide()
        parent = DarkMenu.open_chain[position - 1]
        parent._window.focus_force()
        return "break"


    @classmethod
    def _bind_global_click(cls, master: tk.Misc) -> None:
        if cls._global_click_bound:
            return
        cls._global_click_bound = True
        master.winfo_toplevel().bind_all("<ButtonPress-1>", cls._on_global_click, add="+")

    @classmethod
    def _on_global_click(cls, event: tk.Event) -> None:
        if not cls.open_chain:
            return
        widget = event.widget
        if getattr(widget, "is_menu_button", False):
            return
        try:
            toplevel = widget.winfo_toplevel()
        except (AttributeError, tk.TclError):
            toplevel = None
        if any(toplevel is menu._window for menu in cls.open_chain):
            return
        cls.close_all()

    @classmethod
    def _close_if_app_unfocused(cls) -> None:
        if cls.open_chain:
            try:
                if cls.open_chain[0].master.focus_get() is None:
                    cls.close_all()
            except (KeyError, tk.TclError):
                cls.close_all()
