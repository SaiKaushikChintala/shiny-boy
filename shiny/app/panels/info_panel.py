import tkinter as tk

from shiny.app.ui.kit import Chip
from shiny.app.ui.theme import FONT_SMALL, FONT_TITLE, P, dp
from shiny.app.ui.widgets import Card


class InfoPanel(tk.Frame):
    def __init__(self, parent: tk.Misc, wraplength: int):
        super().__init__(parent, background=P.panel)
        self._cache: dict[tk.Label, tuple[str, str]] = {}

        game = self.card = Card(self)
        game.pack(fill="x", padx=dp(14), pady=(dp(14), dp(10)))
        game.header.pack(fill="x", pady=(0, dp(10)), before=game.grid_body)
        self.game_value = tk.Label(game.header, text="", background=P.card, foreground=P.text, font=FONT_TITLE, anchor="w")
        self.game_value.pack(side="left")
        self.state_chip = Chip(game.header, bg=P.card)
        self.state_chip.pack(side="right")
        self.frame_value = game.row("Frame")
        self.speed_value = game.row("Speed")
        self.advances_value = game.row("Advances")
        self.name_value = game.row("Trainer", mono=False)
        self.ids_value = game.row("ID")
        self.rng_value = game.row("RNG")
        self.map_value = game.row("Map")
        self.tile_value = game.row("Position")

        self.notice = tk.Label(
            self,
            text="",
            background=P.panel,
            foreground=P.warning,
            font=FONT_SMALL,
            justify="left",
            anchor="w",
            wraplength=wraplength,
        )

    def arrange(self, columns: int) -> None:
        self.card.arrange(columns)

    def set_wraplength(self, wraplength: int) -> None:
        self.notice.configure(wraplength=wraplength)

    def _set(self, label: tk.Label, text: str, color: str = P.text) -> None:
        if self._cache.get(label) != (text, color):
            self._cache[label] = (text, color)
            label.configure(text=text, foreground=color)

    def _show(self, label: tk.Label, visible: bool, text: str) -> None:
        self.card.set_visible(label, visible)
        if visible:
            self._set(label, text)

    def _state_chip(self, state: str) -> None:
        if state == "Overworld":
            self.state_chip.set(state, P.accent_text, P.accent_dim)
        elif state == "Battle":
            self.state_chip.set(state, P.danger, P.danger_dim)
        else:
            self.state_chip.set(state, P.muted, P.button)

    def refresh(
        self,
        *,
        game: str,
        frame: int | None,
        fps: float,
        callback: str | None,
        ids: tuple[int, int | None] | None,
        rng: str | None,
        map_group_and_number: tuple[int, int] | None,
        position: tuple[int, int] | None,
        advances: int | None = None,
        notice: str = "",
        name: str | None = None,
        speed: str | None = None,
    ) -> None:
        self._set(self.game_value, game)
        self._show(self.frame_value, frame is not None, "" if frame is None else f"{frame:,}   ·   {fps:.0f} fps")
        self._show(self.speed_value, speed is not None, speed or "")
        self._show(self.advances_value, advances is not None, "" if advances is None else f"{advances:,}")
        if callback is None:
            self.state_chip.pack_forget()
            self.card.header.pack_configure(pady=0)
        else:
            if not self.state_chip.winfo_manager():
                self.state_chip.pack(side="right")
            self.card.header.pack_configure(pady=(0, dp(10)))
            self._state_chip(callback)

        has_ids = not (ids is None or ids == (0, 0) and not name)
        self._show(self.name_value, has_ids and bool(name), name or "")
        if has_ids:
            self._show(self.ids_value, True, f"TID {ids[0]}" if ids[1] is None else f"TID {ids[0]}   SID {ids[1]}   TSV {(ids[0] ^ ids[1]) >> 3}")
        else:
            self._show(self.ids_value, False, "")
        self._show(self.rng_value, rng is not None, rng or "")
        self._show(self.map_value, map_group_and_number is not None, "" if map_group_and_number is None else f"{map_group_and_number[0]}/{map_group_and_number[1]}")
        self._show(self.tile_value, position is not None, "" if position is None else f"x {position[0]}   y {position[1]}")

        if self.notice.cget("text") != notice:
            self.notice.configure(text=notice)
            if notice:
                self.notice.pack(fill="x", padx=dp(16), pady=(0, dp(14)))
            else:
                self.notice.pack_forget()
