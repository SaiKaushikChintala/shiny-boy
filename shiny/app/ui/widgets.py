import tkinter as tk

from shiny.app.ui.theme import FONT, FONT_HEADING, FONT_MONO, FONT_SMALL, P


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
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        self._window = tk.Toplevel(self._widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._window,
            text=self._text,
            background=P.card,
            foreground=P.text,
            font=FONT_SMALL,
            padx=8,
            pady=4,
            borderwidth=1,
            relief="solid",
        ).pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None


class Card(tk.Frame):

    def __init__(self, parent: tk.Misc, title: str):
        super().__init__(parent, background=P.card, highlightthickness=1, highlightbackground=P.border)
        tk.Label(self, text=title.upper(), background=P.card, foreground=P.muted, font=FONT_HEADING).pack(
            anchor="w", padx=12, pady=(8, 2)
        )
        self.body = tk.Frame(self, background=P.card)
        self.body.pack(fill="x", padx=12, pady=(0, 8))
        self.body.columnconfigure(1, weight=1)
        self._rows = 0

    def text_row(self, mono: bool = True) -> tk.Label:
        label = tk.Label(
            self.body,
            text="",
            background=P.card,
            foreground=P.text,
            font=FONT_MONO if mono else FONT,
            anchor="w",
            justify="left",
        )
        label.grid(row=self._rows, column=0, columnspan=2, sticky="we")
        self._rows += 1
        return label

    def row(self, label: str, mono: bool = True) -> tk.Label:
        tk.Label(self.body, text=label, background=P.card, foreground=P.muted, font=FONT, anchor="w", width=8).grid(
            row=self._rows, column=0, sticky="w"
        )
        value_label = tk.Label(
            self.body,
            text="",
            background=P.card,
            foreground=P.text,
            font=FONT_MONO if mono else FONT,
            anchor="w",
            justify="left",
        )
        value_label.grid(row=self._rows, column=1, sticky="we", padx=(4, 0))
        self._rows += 1
        return value_label


class MenuButton(tk.Menubutton):

    is_menu_button = True
    all_buttons: list["MenuButton"] = []

    def __init__(self, parent: tk.Misc, text: str, menu):
        super().__init__(
            parent,
            text=text,
            background=P.panel,
            foreground=P.text,
            activebackground=P.button_hover,
            activeforeground="white",
            font=FONT,
            relief="flat",
            borderwidth=0,
            padx=11,
            pady=6,
            takefocus=0,
        )
        self._menu = menu
        MenuButton.all_buttons.append(self)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", lambda _event: self._paint())
        self.bind("<ButtonPress-1>", self._on_press)

    @property
    def is_open(self) -> bool:
        return self._menu.is_open

    def _paint(self) -> None:
        hovered = self.winfo_containing(*self.winfo_pointerxy()) is self
        self.configure(background=P.button_hover if (self.is_open or hovered) else P.panel)

    def _on_enter(self, _event) -> None:
        self.configure(background=P.button_hover)
        if any(button.is_open for button in MenuButton.all_buttons) and not self.is_open:
            self.open_menu()

    def _on_press(self, _event) -> None:
        if self.is_open:
            self._menu.close()
        else:
            self.open_menu()

    def open_menu(self) -> None:
        self._menu.popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height(), on_close=self._repaint_all)
        self._repaint_all()

    @staticmethod
    def _repaint_all() -> None:
        for button in MenuButton.all_buttons:
            try:
                button._paint()
            except tk.TclError:
                pass
