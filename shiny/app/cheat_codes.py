from pathlib import Path
from typing import TYPE_CHECKING

from shiny.app.ui.cheats_dialog import CheatsDialog
from shiny.core.emulator.cheats import Cheats
from shiny.core.emulator.interface import EmulatorError

if TYPE_CHECKING:
    from shiny.app.window import Viewer


class CheatCodes:
    def __init__(self, app: "Viewer"):
        self.app = app
        self.cheats: Cheats | None = None
        self.dialog: CheatsDialog | None = None

    @property
    def game_key(self) -> str:
        return Path(self.app.rom).stem

    def is_on(self) -> bool:
        return bool(self.cheats is not None and self.cheats.is_on)

    def apply(self, text: str, kind: str) -> list[str]:
        app = self.app
        if not app.emulator.is_gba:
            raise EmulatorError("Cheat codes work for Game Boy Advance games only.")
        if self.cheats is None:
            self.cheats = Cheats(app.emulator)
        self.cheats.remove_all()
        try:
            effects = self.cheats.add(self.game_key, text.splitlines(), kind)
        except EmulatorError:
            app.settings.cheats[self.game_key] = {"text": text, "kind": kind, "on": False}
            app.save_settings()
            raise
        app.settings.cheats[self.game_key] = {"text": text, "kind": kind, "on": True}
        app.save_settings()
        app.set_status("Cheats are on.", "success")
        return effects

    def turn_off(self) -> None:
        if self.cheats is not None:
            self.cheats.remove_all()
        entry = self.app.settings.cheats.get(self.game_key)
        if entry:
            entry["on"] = False
            self.app.save_settings()
        self.app.set_status("Cheats are off.", "info")

    def restore(self) -> None:
        self.cheats = None
        entry = self.app.settings.cheats.get(self.game_key)
        if entry and entry.get("on") and self.app.emulator.is_gba:
            try:
                self.apply(entry["text"], entry.get("kind", "Auto-detect"))
            except EmulatorError as error:
                self.app.set_status(f"The saved cheats could not be switched on: {error}", "warning")

    def show_dialog(self) -> None:
        app = self.app
        if not app.emulator.is_gba:
            app.set_status("Cheat codes work for Game Boy Advance games only.", "warning")
            return
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        entry = app.settings.cheats.get(self.game_key, {})
        self.dialog = CheatsDialog(
            app.window,
            app.emulator.title,
            entry.get("text", ""),
            entry.get("kind", "Auto-detect"),
            self.is_on(),
            self.apply,
            self.turn_off,
            app.focus_game,
        )
