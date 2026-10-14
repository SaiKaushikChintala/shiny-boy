import tkinter as tk
from tkinter import ttk
from typing import Callable

from shiny.app.ui.menus import DarkMenu
from shiny.app.ui.theme import FONT_SMALL, P
from shiny.app.ui.widgets import MenuButton, Tooltip

SPEEDS = ((1, "1×"), (2, "2×"), (4, "4×"), (8, "8×"), (16, "16×"), (32, "32×"), (100, "100×"), (0, "Max"))


class Toolbar(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        menus: dict[str, DarkMenu],
        speed_variable: tk.IntVar,
        on_pause: Callable[[], None],
        on_prev_frame: Callable[[], None],
        on_next_frame: Callable[[], None],
        on_reset: Callable[[], None],
        on_screenshot: Callable[[], None],
        on_speed: Callable[[], None],
    ):
        super().__init__(parent, background=P.panel)
        self.menu_buttons: dict[str, MenuButton] = {}
        for name, menu in menus.items():
            button = MenuButton(self, name, menu)
            button.pack(side="left", padx=(2, 0), pady=4)
            self.menu_buttons[name] = button

        self._divider()
        self.pause_button = self._button("Pause", on_pause, "Pause or resume the game  (P)")
        self._button("Prev", on_prev_frame, "Back one frame (pauses the game)  (,)")
        self._button("Next", on_next_frame, "Forward one frame (pauses the game)  (.)")
        self._button("Reset", on_reset, "Soft-reset the game  (F2)")
        self._button("Screenshot", on_screenshot, "Save a screenshot  (F12)")

        self._divider()
        tk.Label(self, text="Speed", background=P.panel, foreground=P.muted, font=FONT_SMALL).pack(
            side="left", padx=(4, 6)
        )
        for value, label in SPEEDS:
            button = ttk.Radiobutton(
                self,
                text=label,
                value=value,
                variable=speed_variable,
                command=on_speed,
                style="Segment.Toolbutton",
                takefocus=0,
                width=4,
            )
            button.pack(side="left", padx=1, pady=6)
            if value == 0:
                Tooltip(button, "As fast as this computer can (no sound)")
            elif value == 100:
                Tooltip(button, "Tries for 100×; a single emulator manages about 40-50× on most computers")

        tk.Frame(self, background=P.border, height=1).place(relx=0, rely=1, relwidth=1, anchor="sw")

    def open_menu(self, name: str) -> None:
        self.menu_buttons[name].open_menu()

    def _button(self, text: str, command: Callable[[], None], hint: str) -> ttk.Button:
        button = ttk.Button(self, text=text, command=command, style="Tool.TButton", takefocus=0)
        button.pack(side="left", padx=1, pady=5)
        Tooltip(button, hint)
        return button

    def _divider(self) -> None:
        tk.Frame(self, background=P.border, width=1).pack(side="left", fill="y", padx=8, pady=9)

    def set_paused(self, paused: bool) -> None:
        self.pause_button.configure(text="Resume" if paused else "Pause")
