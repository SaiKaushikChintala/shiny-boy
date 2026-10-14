import tkinter as tk

from shiny.app.ui.theme import FONT_SMALL, P
from shiny.app.ui.widgets import Card


class InfoPanel(tk.Frame):
    def __init__(self, parent: tk.Misc, wraplength: int):
        super().__init__(parent, background=P.panel)
        self._cache: dict[tk.Label, tuple[str, str]] = {}

        game = Card(self, "Game")
        game.pack(fill="x", padx=12, pady=(10, 6))
        self.game_value = game.row("Game", mono=False)
        self.frame_value = game.row("Frame")
        self.advances_value = game.row("Advances")
        self.state_value = game.row("State")

        row = tk.Frame(self, background=P.panel)
        row.pack(fill="x", padx=12, pady=(0, 6))
        row.columnconfigure((0, 1, 2), weight=1, uniform="info")

        trainer = Card(row, "Trainer")
        trainer.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        self.name_value = trainer.text_row(mono=False)
        self.tid_value = trainer.text_row()
        self.sid_value = trainer.text_row()
        self.tsv_value = trainer.text_row()

        rng = Card(row, "RNG")
        rng.grid(row=0, column=1, sticky="nsew", padx=3)
        self.rng_value = rng.text_row()

        position = Card(row, "Position")
        position.grid(row=0, column=2, sticky="nsew", padx=(3, 0))
        self.map_value = position.text_row()
        self.tile_value = position.text_row()

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
        self.notice.pack(fill="x", padx=14)

    def _set(self, label: tk.Label, text: str, color: str = P.text) -> None:
        if self._cache.get(label) != (text, color):
            self._cache[label] = (text, color)
            label.configure(text=text, foreground=color)

    def refresh(
        self,
        *,
        game: str,
        frame: int,
        fps: float,
        callback: str,
        ids: tuple[int, int | None] | None,
        rng: str | None,
        map_group_and_number: tuple[int, int] | None,
        position: tuple[int, int] | None,
        advances: int | None = None,
        notice: str = "",
        name: str | None = None,
    ) -> None:
        self._set(self.game_value, game)
        self._set(self.frame_value, f"{frame:,}  ({fps:.0f} fps)")
        self._set(self.advances_value, "—" if advances is None else f"{advances:,}", P.muted if advances is None else P.text)
        self._set(self.state_value, callback, P.accent)

        if ids is None or ids == (0, 0) and not name:
            self._set(self.name_value, "—", P.muted)
            self._set(self.tid_value, "not available", P.muted)
            self._set(self.sid_value, "")
            self._set(self.tsv_value, "")
        else:
            self._set(self.name_value, name or "—")
            self._set(self.tid_value, f"TID {ids[0]}")
            if ids[1] is None:
                self._set(self.sid_value, "")
                self._set(self.tsv_value, "")
            else:
                self._set(self.sid_value, f"SID {ids[1]}")
                self._set(self.tsv_value, f"TSV {(ids[0] ^ ids[1]) >> 3}")

        self._set(self.rng_value, "—" if rng is None else rng)
        self._set(self.map_value, "Map —" if map_group_and_number is None else f"Map {map_group_and_number[0]}/{map_group_and_number[1]}")
        self._set(self.tile_value, "—" if position is None else f"x {position[0]}  y {position[1]}")

        self.notice.configure(text=notice)
