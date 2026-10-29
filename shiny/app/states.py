import gc
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from tkinter import filedialog
from typing import TYPE_CHECKING

from shiny.core.emulator.interface import EmulatorError
from shiny.core.emulator.mgba_backend import Emulator
from shiny.core.scan.engine import ScriptFailed
from shiny.games.detect import open_reader
from shiny.games.gen3 import savegame
from shiny.games.gen3.savegame import RELOAD_CLOCK
from shiny.paths import ROMS_DIRECTORY, SAVES_DIRECTORY, SCREENSHOTS_DIRECTORY, STATES_DIRECTORY

if TYPE_CHECKING:
    from shiny.app.window import Viewer

SLOT_COUNT = 10
SLOTS_PER_BANK = 10
BANK_COUNT = SLOT_COUNT // SLOTS_PER_BANK

SAVE_FILE_TYPES = [("Save games (.sav, .srm)", "*.sav *.srm"), ("All files", "*.*")]
ROM_FILE_TYPES = [("Game Boy ROMs (GBA, GB, GBC)", "*.gba *.gb *.gbc *.sgb *.zip"), ("All files", "*.*")]
STATE_FILE_TYPES = [("Save states", " ".join(f"*.ss{number}" for number in range(10)))]


def find_active_save(rom: Path) -> Path:
    save = SAVES_DIRECTORY / f"{rom.stem}.sav"
    if not save.exists() and (SAVES_DIRECTORY / f"{rom.stem}.srm").exists():
        return SAVES_DIRECTORY / f"{rom.stem}.srm"
    return save


def open_game(path: Path):
    save_path = find_active_save(path)
    emulator = Emulator(path, save_path)
    return emulator, open_reader(emulator), save_path


class GameFiles:
    def __init__(self, app: "Viewer"):
        self.app = app
        self.slot_bank = 0
        self.save_backed_up = False

    def slot_path(self, slot: int) -> Path:
        return STATES_DIRECTORY / f"{self.app.rom.stem}.slot{slot}.ss1"

    def slot_for_key(self, key: str) -> int:
        return self.slot_bank * SLOTS_PER_BANK + (SLOTS_PER_BANK if key == "0" else int(key))

    def change_slot_bank(self, step: int) -> None:
        self.slot_bank = (self.slot_bank + step) % BANK_COUNT
        first = self.slot_bank * SLOTS_PER_BANK + 1
        self.app.set_status(f"The number keys now reach slots {first} - {first + SLOTS_PER_BANK - 1}.", "info")

    def save_slot(self, slot: int) -> None:
        if not self.app.require_game():
            return
        self.app.emulator.save_state_file(self.slot_path(slot))
        self.app.set_status(f"State saved to slot {slot}.", "success")

    def load_slot(self, slot: int) -> None:
        path = self.slot_path(slot)
        if not path.is_file():
            self.app.set_status(f"Slot {slot} is empty.", "warning")
            return
        self.load_state(path, f"slot {slot}")

    def load_state(self, path: Path, description: str) -> None:
        if self.app.bots.is_active():
            return
        try:
            self.app.emulator.load_state_file(path)
        except EmulatorError as error:
            self.app.set_status(f"Could not load state: {error}", "error")
            return
        self.app.loop.history.clear()
        self.app.set_status(f"State loaded from {description}.", "success")

    @contextmanager
    def dialog_open(self):
        loop = self.app.loop
        loop.paused = True
        try:
            yield
        finally:
            self.app.window.focus_force()
            loop.restart_clock()
            self.app.reset_inputs()
            loop.paused = False

    def load_state_from_file(self) -> None:
        STATES_DIRECTORY.mkdir(parents=True, exist_ok=True)
        with self.dialog_open():
            chosen = filedialog.askopenfilename(
                parent=self.app.window, title="Load a save state", initialdir=str(STATES_DIRECTORY), filetypes=STATE_FILE_TYPES + [("All files", "*.*")]
            )
        if chosen:
            self.load_state(Path(chosen), Path(chosen).name)

    def save_state_to_file(self) -> None:
        if not self.app.require_game():
            return
        STATES_DIRECTORY.mkdir(parents=True, exist_ok=True)
        with self.dialog_open():
            chosen = filedialog.asksaveasfilename(
                parent=self.app.window,
                title="Create a save state file",
                initialdir=str(STATES_DIRECTORY),
                initialfile=f"{self.app.rom.stem}_{time.strftime('%Y-%m-%d_%H-%M-%S')}.ss1",
                defaultextension=".ss1",
                filetypes=STATE_FILE_TYPES,
            )
        if chosen:
            self.app.emulator.save_state_file(Path(chosen))
            self.app.set_status(f"State saved to {Path(chosen).name}.", "success")

    def take_screenshot(self) -> None:
        if not self.app.require_game():
            return
        SCREENSHOTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOTS_DIRECTORY / f"{self.app.rom.stem}_{time.strftime('%Y-%m-%d_%H-%M-%S')}.png"
        self.app.emulator.screenshot(path)
        self.app.set_status(f"Screenshot saved: {path.name}", "success")

    def reset(self) -> None:
        if self.app.bots.is_active() or not self.app.require_game():
            return
        self.app.emulator.reset()
        self.app.loop.history.clear()
        self.app.set_status("Game reset.")

    def import_save(self, source: Path) -> None:
        app = self.app
        if app.bots.is_active() or not app.require_game():
            return
        SAVES_DIRECTORY.mkdir(parents=True, exist_ok=True)
        target = SAVES_DIRECTORY / f"{app.rom.stem}.sav"
        incoming = SAVES_DIRECTORY / f"{app.rom.stem}.incoming"
        replaced = False
        try:
            if source.resolve() != target.resolve():
                shutil.copyfile(source, incoming)
                app.emulator.load_save_file(incoming)
                gc.collect()
                if target.exists():
                    shutil.copyfile(target, target.with_name(target.name + ".bak"))
                    replaced = True
                shutil.copyfile(incoming, target)
            app.emulator.load_save_file(target)
            gc.collect()
            incoming.unlink(missing_ok=True)
        except (EmulatorError, OSError) as error:
            app.set_status(f"Could not load save: {error}", "error")
            return
        app.save_path = target
        note = f"; the one it replaced is kept as {target.name}.bak" if replaced else ""
        app.set_status(f"Save loaded: {source.name} (game reset){note}", "success")

    def load_save_from_file(self) -> None:
        SAVES_DIRECTORY.mkdir(parents=True, exist_ok=True)
        with self.dialog_open():
            chosen = filedialog.askopenfilename(parent=self.app.window, title="Load a save game", initialdir=str(SAVES_DIRECTORY), filetypes=SAVE_FILE_TYPES)
        if chosen:
            self.load_save_of_any_game(Path(chosen))

    @staticmethod
    def rom_for_save(save: Path) -> Path | None:
        name = save.name
        for suffix in (".bak", ".sav", ".srm"):
            if name.lower().endswith(suffix):
                name = name[: -len(suffix)]
        for rom in ROMS_DIRECTORY.glob("*"):
            if rom.is_file() and rom.stem == name:
                return rom
        return None

    def load_save_of_any_game(self, save: Path) -> None:
        owner = self.rom_for_save(save)
        if owner is None and not self.app.require_game():
            return
        if owner is None or owner.resolve() == Path(self.app.rom).resolve():
            self.import_save(save)
            return
        if not self.load_rom(owner):
            return
        self.import_save(save)
        self.app.set_status(f"Opened {owner.name} with the save {save.name} (game reset).", "success")

    def load_rom_from_file(self) -> None:
        ROMS_DIRECTORY.mkdir(parents=True, exist_ok=True)
        folder = Path(self.app.rom).parent if Path(self.app.rom).parent.is_dir() else ROMS_DIRECTORY
        with self.dialog_open():
            chosen = filedialog.askopenfilename(parent=self.app.window, title="Load a ROM", initialdir=str(folder), filetypes=ROM_FILE_TYPES)
        if chosen:
            self.load_rom(Path(chosen))

    def load_rom(self, path: Path) -> bool:
        app = self.app
        if app.bots.is_active():
            return False
        save_existed = find_active_save(path).exists()
        try:
            emulator, game, save_path = open_game(path)
        except Exception as error:
            gc.collect()
            if not save_existed:
                try:
                    find_active_save(path).unlink(missing_ok=True)
                except OSError:
                    pass
            app.set_status(f"Could not open {path.name}: {error}", "error")
            return False
        app.switch_game(emulator, game, path, save_path)
        app.set_status(f"Loaded {path.name}", "success")
        return True

    def back_up_save(self) -> None:
        save_path = self.app.save_path
        if self.save_backed_up or not save_path.is_file():
            return
        self.save_backed_up = True
        if any(byte != 0xFF for byte in save_path.read_bytes()):
            shutil.copyfile(save_path, save_path.with_name(save_path.name + ".bak"))

    def _flush_audio(self) -> None:
        for _ in range(4):
            self.app.emulator.read_audio()

    def save_game(self) -> bool:
        app = self.app
        try:
            self.back_up_save()
            app.game.save_in_game(app.bots.save_bytes() or b"")
            state = app.emulator.get_state()
            app.emulator.load_save_file(app.save_path)
            app.emulator.set_state(state)
        except (ScriptFailed, EmulatorError) as error:
            app.bots.refuse(str(error))
            return False
        self._flush_audio()
        app.loop.history.clear()
        app.loop.restart_clock()
        return True

    def reload_game(self) -> bool:
        app = self.app
        try:
            app.emulator.set_fixed_clock(RELOAD_CLOCK)
            savegame.reload_from_save(app.emulator, app.game)
        except (ScriptFailed, EmulatorError) as error:
            app.bots.refuse(str(error))
            return False
        app.emulator.use_real_clock()
        app.reset_inputs()
        self._flush_audio()
        app.loop.history.clear()
        app.loop.restart_clock()
        return True
