import tkinter as tk

from shiny.app.ui.kit import Button, RoundedFrame
from shiny.app.ui.theme import FONT, FONT_HEADING, FONT_MONO, FONT_SMALL, P, dp


class Tooltip:

    def __init__(self, widget: tk.Misc, text: str, delay_ms: int = 450):
        self._widget = widget
        self._text = text
        self._delay = delay_ms
        self._job = None
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._job = self._widget.after(self._delay, self._show)

    def _cancel(self) -> None:
        if self._job is not None:
            self._widget.after_cancel(self._job)
            self._job = None

    def _show(self) -> None:
        self._job = None
        if self._window is not None:
            return
        x = self._widget.winfo_rootx()
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + dp(6)
        self._window = tk.Toplevel(self._widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        self._window.configure(background=P.border_strong)
        tk.Label(
            self._window,
            text=self._text,
            background=P.card,
            foreground=P.text,
            font=FONT_SMALL,
            padx=dp(10),
            pady=dp(6),
        ).pack(padx=1, pady=1)

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None


class Card(RoundedFrame):

    def __init__(self, parent: tk.Misc, title: str = ""):
        super().__init__(parent, radius=14, fill=P.card, outline=P.border, pad=16)
        self.header = tk.Frame(self.body, background=P.card)
        if title:
            self.header.pack(fill="x", pady=(0, dp(8)))
            tk.Label(self.header, text=title.upper(), background=P.card, foreground=P.subtle, font=FONT_HEADING).pack(side="left")
        self.grid_body = tk.Frame(self.body, background=P.card)
        self.grid_body.pack(fill="x")
        self.grid_body.columnconfigure(1, weight=1)
        self._rows = 0
        self.row_widgets: list[tuple[tk.Label, tk.Label]] = []
        self._hidden: set[tk.Label] = set()
        self._columns = 1

    def row(self, label: str, mono: bool = True) -> tk.Label:
        name_label = tk.Label(self.grid_body, text=label, background=P.card, foreground=P.subtle, font=FONT_SMALL, anchor="w", width=9)
        name_label.grid(row=self._rows, column=0, sticky="w", pady=dp(3))
        value_label = tk.Label(
            self.grid_body,
            text="",
            background=P.card,
            foreground=P.text,
            font=FONT_MONO if mono else FONT,
            anchor="w",
            justify="left",
        )
        value_label.grid(row=self._rows, column=1, sticky="we", padx=(dp(4), 0), pady=dp(3))
        self._rows += 1
        self.row_widgets.append((name_label, value_label))
        return value_label

    def set_visible(self, value_label: tk.Label, visible: bool) -> None:
        if visible == (value_label not in self._hidden):
            return
        (self._hidden.discard if visible else self._hidden.add)(value_label)
        self.arrange(self._columns)

    def arrange(self, columns: int) -> None:
        self._columns = columns
        shown = [pair for pair in self.row_widgets if pair[1] not in self._hidden]
        for name_label, value_label in self.row_widgets:
            if value_label in self._hidden:
                name_label.grid_remove()
                value_label.grid_remove()
        per_column = max(1, -(-len(shown) // columns))
        for column in range(4):
            self.grid_body.columnconfigure(column, weight=0)
        for index, (name_label, value_label) in enumerate(shown):
            row, group = index % per_column, index // per_column
            name_label.grid(row=row, column=2 * group, sticky="w", padx=(dp(24) if group else 0, 0))
            value_label.grid(row=row, column=2 * group + 1, sticky="we", padx=(dp(4), 0))
        for group in range(columns):
            self.grid_body.columnconfigure(2 * group + 1, weight=1, uniform="values")


class MenuButton(Button):

    is_menu_button = True
    all_buttons: list["MenuButton"] = []

    def __init__(self, parent: tk.Misc, text: str, menu):
        super().__init__(parent, text, kind="ghost", padx=12, pady=6, font=FONT, radius=8)
        self._menu = menu
        MenuButton.all_buttons.append(self)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", lambda _event: self._paint())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", lambda _event: None)

    @property
    def is_open(self) -> bool:
        return self._menu.is_open

    def _paint(self) -> None:
        hovered = self.winfo_containing(*self.winfo_pointerxy()) is self
        self._set(hover=self.is_open or hovered)

    def _on_enter(self, _event) -> None:
        self._set(hover=True)
        if any(button.is_open for button in MenuButton.all_buttons) and not self.is_open:
            self.open_menu()

    def _on_press(self, _event) -> None:
        if self.is_open:
            self._menu.close()
        else:
            self.open_menu()

    def open_menu(self) -> None:
        self._menu.popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + dp(4), on_close=self._repaint_all)
        self._repaint_all()

    @staticmethod
    def _repaint_all() -> None:
        for button in MenuButton.all_buttons:
            try:
                button._paint()
            except tk.TclError:
                pass
