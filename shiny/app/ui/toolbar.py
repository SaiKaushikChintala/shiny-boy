import tkinter as tk
from typing import Callable

from shiny.app.ui.kit import Button, Segmented
from shiny.app.ui.menus import DarkMenu
from shiny.app.ui.theme import FONT_SMALL, P, dp
from shiny.app.ui.widgets import MenuButton, Tooltip

SPEEDS = ((1, "1×"), (2, "2×"), (4, "4×"), (8, "8×"), (16, "16×"), (32, "32×"), (100, "100×"), (0, "Max"))
SPEED_TIPS = {
    0: "As fast as this computer can (no sound)",
    100: "Tries for 100×; a single emulator manages about 40-50× on most computers",
}


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
        on_panel: Callable[[], None],
    ):
        super().__init__(parent, background=P.panel)
        inner = tk.Frame(self, background=P.panel)
        inner.pack(fill="x", padx=dp(10), pady=dp(8))
        self.menu_buttons: dict[str, MenuButton] = {}
        for name, menu in menus.items():
            button = MenuButton(inner, name, menu)
            button.pack(side="left", padx=(0, dp(2)))
            self.menu_buttons[name] = button

        self._divider(inner)
        self.pause_button = self._button(inner, "Pause", on_pause, "Pause or resume the game  (P)")
        self._button(inner, "Prev", on_prev_frame, "Back one frame (pauses the game)  (,)")
        self._button(inner, "Next", on_next_frame, "Forward one frame (pauses the game)  (.)")
        self._button(inner, "Reset", on_reset, "Soft-reset the game  (F2)")
        self._button(inner, "Screenshot", on_screenshot, "Save a screenshot  (F12)")

        self._divider(inner)
        tk.Label(inner, text="SPEED", background=P.panel, foreground=P.subtle, font=FONT_SMALL).pack(side="left", padx=(dp(2), dp(8)))
        Segmented(inner, list(SPEEDS), speed_variable, command=on_speed, tips=SPEED_TIPS, bg=P.panel, padx=10).pack(side="left")

        self.panel_button = Button(inner, "Hide panel", on_panel, kind="secondary", padx=14, pady=6, font=FONT_SMALL, radius=8)
        self.panel_button.pack(side="right")
        Tooltip(self.panel_button, "Hide or show the side panel  (Tab)")

        tk.Frame(self, background=P.border, height=1).place(relx=0, rely=1, relwidth=1, anchor="sw")

    def open_menu(self, name: str) -> None:
        self.menu_buttons[name].open_menu()

    def _button(self, parent: tk.Misc, text: str, command: Callable[[], None], hint: str) -> Button:
        button = Button(parent, text, command, kind="ghost", padx=12, pady=6, font=FONT_SMALL, radius=8)
        button.pack(side="left", padx=dp(1))
        Tooltip(button, hint)
        return button

    def _divider(self, parent: tk.Misc) -> None:
        tk.Frame(parent, background=P.border, width=1, height=dp(20)).pack(side="left", padx=dp(10))

    def set_panel_open(self, is_open: bool) -> None:
        self.panel_button.configure(text="Hide panel" if is_open else "Show panel")

    def set_paused(self, paused: bool) -> None:
        self.pause_button.configure(text="Resume" if paused else "Pause")
