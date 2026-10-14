import tkinter as tk
from tkinter import ttk
from typing import Callable

from shiny.app.ui.theme import FONT, FONT_BOLD, FONT_MONO, FONT_SMALL, P
from shiny.core.emulator.cheats import CHEAT_TYPES
from shiny.core.emulator.interface import EmulatorError

HELP = (
    "Type or paste the codes of a Game Boy Advance game (GameShark, Action Replay or CodeBreaker), one line each, "
    "like  XXXXXXXX XXXXXXXX. The lines of one cheat go together. Lines are not case sensitive."
)
WARNING = (
    "Cheats change the game itself and are not part of a save state. Turn them off before starting a bot or making "
    "a state to hunt from, or the timing will not match."
)


class CheatsDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        game_name: str,
        text: str,
        kind: str,
        is_on: bool,
        on_apply: Callable[[str, str], list[str]],
        on_turn_off: Callable[[], None],
        on_close: Callable[[], None],
    ):
        super().__init__(parent)
        self.title(f"Cheat codes: {game_name}")
        self.configure(background=P.panel)
        self.transient(parent)
        self.minsize(560, 480)
        self._on_apply, self._on_turn_off, self._on_close = on_apply, on_turn_off, on_close

        tk.Label(self, text=HELP, background=P.panel, foreground=P.muted, font=FONT_SMALL, wraplength=520, justify="left",
                 anchor="w").pack(fill="x", padx=18, pady=(16, 8))

        frame = tk.Frame(self, background=P.border)
        frame.pack(fill="both", expand=True, padx=18)
        self.text = tk.Text(
            frame, height=10, width=44, background=P.bg, foreground=P.text, insertbackground=P.text, font=FONT_MONO,
            relief="flat", borderwidth=0, padx=10, pady=8, wrap="none", undo=True, selectbackground=P.accent_dim,
        )
        self.text.pack(fill="both", expand=True, padx=1, pady=1)
        self.text.insert("1.0", text)

        row = tk.Frame(self, background=P.panel)
        row.pack(fill="x", padx=18, pady=(10, 4))
        tk.Label(row, text="Code type", background=P.panel, foreground=P.muted, font=FONT).pack(side="left")
        self.kind = tk.StringVar(value=kind if kind in CHEAT_TYPES else "Auto-detect")
        ttk.Combobox(row, textvariable=self.kind, values=list(CHEAT_TYPES), state="readonly", width=16).pack(side="left", padx=10)
        self.state_label = tk.Label(row, background=P.panel, font=FONT_BOLD)
        self.state_label.pack(side="right")

        buttons = tk.Frame(self, background=P.panel)
        buttons.pack(fill="x", padx=18, pady=(4, 8))
        ttk.Button(buttons, text="Apply", style="Accent.TButton", command=self.apply).pack(side="left")
        ttk.Button(buttons, text="Turn off", command=self.turn_off).pack(side="left", padx=8)
        ttk.Button(buttons, text="Close", command=self.close).pack(side="right")

        self.result = tk.Label(self, background=P.panel, foreground=P.text, font=FONT_MONO, wraplength=520, justify="left",
                               anchor="nw")
        self.result.pack(fill="x", padx=18, pady=(0, 6))
        tk.Label(self, text=WARNING, background=P.panel, foreground=P.warning, font=FONT_SMALL, wraplength=520,
                 justify="left", anchor="w").pack(fill="x", padx=18, pady=(0, 16))

        self.show_state(is_on)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        self.text.focus_set()

    def show_state(self, is_on: bool) -> None:
        self.state_label.configure(text="● On" if is_on else "○ Off", foreground=P.success if is_on else P.muted)

    def apply(self) -> None:
        lines = [line.strip() for line in self.text.get("1.0", "end").splitlines() if line.strip()]
        if not lines:
            self.result.configure(text="Type some codes first.", foreground=P.warning)
            return
        try:
            effects = self._on_apply("\n".join(lines), self.kind.get())
        except EmulatorError as error:
            self.result.configure(text=str(error), foreground=P.danger)
            self.show_state(False)
            return
        self.result.configure(text="Switched on:\n" + "\n".join(effects), foreground=P.text)
        self.show_state(True)

    def turn_off(self) -> None:
        self._on_turn_off()
        self.result.configure(text="Cheats are off. (The codes stay here, ready to apply again.)", foreground=P.muted)
        self.show_state(False)

    def close(self) -> None:
        self.destroy()
        self._on_close()
