import json
from dataclasses import dataclass
from functools import cache

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorError, EmulatorInterface
from shiny.core.pokemon.gb_model import GbPokemon
from shiny.core.scan.engine import ScriptFailed
from shiny.paths import DATA_DIRECTORY

TEXT_END = 0x50
SCREEN_WIDTH, SCREEN_HEIGHT = 20, 18
CURSOR_TILE = 0xED
SAVE_MENU_TRIES = 12


@cache
def load_symbols(generation: int) -> dict[str, dict[str, tuple[int, int]]]:
    raw = json.loads((DATA_DIRECTORY / f"gen{generation}" / "symbols.json").read_text(encoding="utf-8"))
    return {game: {name: (bank, address) for name, (bank, address) in symbols.items()} for game, symbols in raw.items()}


def decode_text(raw: bytes, stop_at_end: bool = True) -> str:
    letters = []
    for byte in raw:
        if byte == TEXT_END and stop_at_end:
            break
        if 0x80 <= byte <= 0x99:
            letters.append(chr(ord("A") + byte - 0x80))
        elif 0xA0 <= byte <= 0xB9:
            letters.append(chr(ord("a") + byte - 0xA0))
        elif 0xF6 <= byte <= 0xFF:
            letters.append(str(byte - 0xF6))
        else:
            letters.append({0x7F: " ", 0xE3: "-", 0xE7: "!", 0xE6: "?", 0xE8: "."}.get(byte, "·"))
    return "".join(letters).strip()


def press(emu: EmulatorInterface, key: int, frames: int) -> None:
    emu.set_keys(key)
    for _ in range(frames):
        emu.run_frame()


def tap(emu: EmulatorInterface, key: int, wait: int = 25) -> None:
    press(emu, key, 4)
    press(emu, 0, wait)


@dataclass(frozen=True)
class PartyLayout:

    structure: str
    dv_offset: int
    size: int
    made_symbol: str
    made_step: int


class GameBoyReader:

    generation: int
    party: PartyLayout
    battle_symbol: str

    def __init__(self, emulator: EmulatorInterface, key: str):
        self.emulator = emulator
        self.key = key
        self.symbols = load_symbols(self.generation)[key]
        self.name = {"POKEMON_GLD": "Gold", "POKEMON_SLV": "Silver"}.get(getattr(emulator, "title", ""), key.title())

    def symbol(self, name: str) -> tuple[int, int]:
        try:
            return self.symbols[name]
        except KeyError:
            raise EmulatorError(f"Unknown symbol: {name}") from None

    def byte(self, name: str, offset: int = 0) -> int:
        bank, address = self.symbol(name)
        return self.emulator.read_u8(address + offset, bank or None)

    def read(self, name: str, size: int = 1, offset: int = 0) -> bytes:
        bank, address = self.symbol(name)
        return self.emulator.read_bytes(address + offset, size, bank or None)

    def write(self, name: str, data: bytes, offset: int = 0) -> None:
        bank, address = self.symbol(name)
        self.emulator.write_bytes(address + offset, data, bank or None)

    def trainer_ids(self) -> tuple[int, None]:
        data = self.read("wPlayerID", 2)
        return data[0] << 8 | data[1], None

    def trainer_name(self) -> str | None:
        return decode_text(self.read("wPlayerName", 11)) or None

    def rng_text(self) -> str:
        return f"{self.byte('hRandomAdd'):#04x} {self.byte('hRandomAdd', 1):#04x}"

    def advances(self) -> None:
        return None

    def player_position(self) -> tuple[int, int]:
        return self.byte("wXCoord"), self.byte("wYCoord")

    def in_battle(self) -> bool:
        return self.byte(self.battle_symbol) != 0

    def in_overworld(self) -> bool:
        return not self.in_battle()

    def state_name(self) -> str:
        return "Battle" if self.in_battle() else "Overworld"

    def species_name(self, species: int) -> str:
        raise NotImplementedError

    def party_size(self) -> int:
        return self.byte("wPartyCount")

    def party_pokemon_made(self, index: int) -> bool:
        return self.byte(self.party.made_symbol, index * self.party.made_step) != 0

    def party_pokemon(self, index: int) -> GbPokemon:
        dvs = self.read(self.party.structure, 2, self.party.dv_offset + index * self.party.size)
        species = self.byte("wPartySpecies", index)
        return GbPokemon(species, self.species_name(species), (dvs[0], dvs[1]), self.generation)

    def newest_party_pokemon(self) -> GbPokemon:
        return self.party_pokemon(self.party_size() - 1)

    def enemy_species(self) -> int:
        return self.byte("wEnemyMonSpecies")

    def enemy_pokemon(self) -> GbPokemon:
        dvs = self.read("wEnemyMonDVs", 2)
        species = self.byte("wEnemyMonSpecies")
        return GbPokemon(species, self.species_name(species), (dvs[0], dvs[1]), self.generation)

    def screen_rows(self) -> list[str]:
        raw = self.read(self.tilemap_symbol, SCREEN_WIDTH * SCREEN_HEIGHT)
        return [decode_text(raw[row * SCREEN_WIDTH : (row + 1) * SCREEN_WIDTH], False) for row in range(SCREEN_HEIGHT)]

    def screen_has(self, *words: str) -> bool:
        text = " ".join(self.screen_rows())
        return all(word in text for word in words)

    def cursor_row(self) -> int | None:
        raw = self.read(self.tilemap_symbol, SCREEN_WIDTH * SCREEN_HEIGHT)
        for index, tile in enumerate(raw):
            if tile == CURSOR_TILE:
                return index // SCREEN_WIDTH
        return None

    def save_in_game(self, save_data: bytes = b"") -> None:
        emu = self.emulator
        tap(emu, Button.START, 30)
        for _ in range(SAVE_MENU_TRIES):
            if self.screen_has("SAVE"):
                break
            tap(emu, Button.START, 30)
        else:
            raise ScriptFailed("The menu did not open. Be in the overworld (not in a menu, a battle or a cutscene) to save.")
        for _ in range(SAVE_MENU_TRIES):
            rows = self.screen_rows()
            wanted = next((index for index, text in enumerate(rows) if "SAVE" in text), None)
            here = self.cursor_row()
            if wanted is None or here is None:
                tap(emu, Button.DOWN, 10)
                continue
            if here == wanted:
                break
            tap(emu, Button.DOWN if here < wanted else Button.UP, 12)
        else:
            raise ScriptFailed("Could not put the cursor on SAVE.")
        tap(emu, Button.A, 60)
        tap(emu, Button.A, 60)
        for _ in range(SAVE_MENU_TRIES):
            if self.screen_has("saved"):
                break
            tap(emu, Button.A, 90)
        for _ in range(10):
            tap(emu, Button.B, 30)
