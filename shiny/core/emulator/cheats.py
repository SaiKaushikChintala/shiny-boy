from mgba import ffi, lib

from shiny.core.emulator.interface import EmulatorError
from shiny.core.emulator.mgba_backend import Emulator

CHEAT_TYPES = {"Auto-detect": 0, "CodeBreaker": 1, "GameShark": 2, "Action Replay": 3}


class Cheats:

    def __init__(self, emulator: Emulator):
        if not emulator.is_gba:
            raise EmulatorError("Cheat codes are only supported for Game Boy Advance games here.")
        core = emulator.native_core
        device = core.cheatDevice(core)
        if device == ffi.NULL:
            raise EmulatorError("This game has no cheat device.")
        self._emulator = emulator
        self._device = device
        self._sets: list = []
        self._original_rom: list[tuple[int, bytes]] = []

    def add(self, name: str, lines: list[str], kind: str = "Auto-detect") -> list[str]:
        cheat_set = self._device.createSet(self._device, name.encode())
        if cheat_set == ffi.NULL:
            raise EmulatorError("Could not create the cheat.")
        for line in lines:
            if not lib.mCheatAddLine(cheat_set, line.encode(), CHEAT_TYPES[kind]):
                lib.mCheatSetDeinit(cheat_set)
                raise EmulatorError(f"This line is not a valid {kind} code: {line}")
        lib.mCheatAddSet(self._device, cheat_set)
        self._sets.append(cheat_set)
        for i in range(cheat_set.romPatches.size):
            patch = cheat_set.romPatches.vector[i]
            self._original_rom.append((patch.address, self._emulator.read_bytes(patch.address, patch.width)))
        what = [describe(cheat_set.list.vector[i]) for i in range(cheat_set.list.size)]
        what += [
            f"ROM patch  {patch.width}-byte  address {patch.address:#010x}  value {patch.value:#x}"
            for patch in (cheat_set.romPatches.vector[i] for i in range(cheat_set.romPatches.size))
        ]
        return what

    @property
    def is_on(self) -> bool:
        return bool(self._sets)

    def remove_all(self) -> None:
        for cheat_set in self._sets:
            lib.mCheatRemoveSet(self._device, cheat_set)
        self._sets.clear()
        for address, original in reversed(self._original_rom):
            self._emulator.write_rom(address, original)
        self._original_rom.clear()

    def decode(self, lines: list[str], kind: str) -> list[str]:
        descriptions = self.add("preview", lines, kind)
        self.remove_all()
        return descriptions


TYPE_NAMES = ["assign", "assign (indirect)", "and", "add", "or", "if ==", "if !=", "if <", "if >", "if < (unsigned)",
              "if > (unsigned)", "if &", "if (logical and)", "if not and", "if button", "never"]


def describe(cheat) -> str:
    name = TYPE_NAMES[cheat.type] if 0 <= cheat.type < len(TYPE_NAMES) else str(cheat.type)
    return f"{name}  {cheat.width}-byte  address {cheat.address:#010x}  value {cheat.operand:#x}  repeat {cheat.repeat}"
