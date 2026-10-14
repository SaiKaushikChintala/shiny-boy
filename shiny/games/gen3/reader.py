import datetime

from shiny.core.emulator.interface import EmulatorError, EmulatorInterface
from shiny.core.pokemon.model import PARTY_POKEMON_SIZE, PartyPokemon, parse_party_pokemon
from shiny.core.rng import lcrng
from shiny.games.gen3 import layout


def load_symbols(file_name: str) -> dict[str, tuple[int, int]]:
    symbols: dict[str, tuple[int, int]] = {}
    for directory in (layout.SYMBOLS_DIRECTORY, layout.SYMBOLS_DIRECTORY / "patches"):
        with open(directory / file_name) as file:
            for line in file:
                parts = line.split()
                if len(parts) != 4 or parts[3].startswith(".gcc2_compiled"):
                    continue
                address, _flags, size, name = parts
                symbols[name.upper()] = (int(address, 16), int(size, 16))
    return symbols


def rtc_seed(when: datetime.datetime) -> int:
    days = (when.date() - datetime.date(2000, 1, 1)).days + 1
    if when.year > 2000:
        days -= 366
    minutes = 1440 * days + 960 * (when.hour // 10) + 60 * (when.hour % 10) + 16 * (when.minute // 10) + (when.minute % 10)
    return (minutes >> 16) ^ (minutes & 0xFFFF)


class Gen3Reader:
    def __init__(self, emulator: EmulatorInterface):
        self.emulator = emulator

        header = emulator.read_bytes(layout.HEADER_CODE_ADDRESS, 4)
        if not all(0x20 <= byte < 0x7F for byte in header):
            raise EmulatorError("This is not a Pokémon game.")
        code = header.decode("ascii")
        game = layout.GAMES.get(code[:3])
        if game is None or code[3] != layout.LANGUAGE:
            raise EmulatorError(f"Only the English versions of Pokémon Ruby, Sapphire, Emerald, FireRed and LeafGreen are supported (this ROM's game code is {code}).")
        if emulator.read_bytes(layout.HEADER_REVISION_ADDRESS, 1)[0] != layout.SUPPORTED_REVISION:
            raise EmulatorError(f"Only the first version (revision 0) of Pokémon {game.name} is supported.")

        self.game = game
        self.key = game.key
        self.boot_seed_value: int | None = None
        self.symbols = load_symbols(game.symbol_file)
        self._names_by_address: dict[int, str] | None = None


    def symbol(self, name: str) -> tuple[int, int]:
        try:
            return self.symbols[name.upper()]
        except KeyError:
            raise EmulatorError(f"Unknown symbol: {name}") from None

    def read_symbol(self, name: str, offset: int = 0, size: int = 0) -> bytes:
        address, length = self.symbol(name)
        return self.emulator.read_bytes(address + offset, size if size > 0 else length)

    def symbol_name_at(self, address: int) -> str | None:
        if self._names_by_address is None:
            self._names_by_address = {symbol[0]: name for name, symbol in self.symbols.items()}
        return self._names_by_address.get(address)


    @property
    def rng_address(self) -> int:
        return self.symbol("gRngValue")[0]

    def rng_value(self) -> int:
        return int.from_bytes(self.read_symbol("gRngValue"), "little")

    def boot_seed(self) -> int | None:
        if self.key == "emerald":
            return 0
        if self.boot_seed_value is not None:
            return self.boot_seed_value
        if self.game.fixed_save_blocks:
            from shiny.games.gen3.savegame import RELOAD_CLOCK

            return rtc_seed(RELOAD_CLOCK)
        return None

    def advances(self) -> int | None:
        seed = self.boot_seed()
        return None if seed is None else lcrng.distance(seed, self.rng_value())

    def rng_text(self) -> str:
        return f"{self.rng_value():#010x}"

    def state_name(self) -> str:
        return self.callback_name()

    def callback_name(self) -> str:
        pointer = int.from_bytes(self.read_symbol("gMain", 4, 4), "little") - 1
        return self.symbol_name_at(pointer) or hex(pointer)

    def in_overworld(self) -> bool:
        return self.callback_name() == "CB2_OVERWORLD"

    def active_tasks(self) -> set[str]:
        data = self.read_symbol("gTasks")
        names = set()
        for index in range(layout.TASK_COUNT):
            task = data[index * layout.TASK_SIZE : (index + 1) * layout.TASK_SIZE]
            pointer = int.from_bytes(task[:4], "little")
            if task[4] != 0 and pointer != 0:
                name = self.symbol_name_at(pointer - 1)
                if name is not None and name != "TASKDUMMY":
                    names.add(name)
        return names

    def task_data(self, name: str, count: int = 4) -> list[int] | None:
        data = self.read_symbol("gTasks")
        for index in range(layout.TASK_COUNT):
            task = data[index * layout.TASK_SIZE : (index + 1) * layout.TASK_SIZE]
            pointer = int.from_bytes(task[:4], "little")
            if task[4] != 0 and pointer != 0 and self.symbol_name_at(pointer - 1) == name.upper():
                return [int.from_bytes(task[8 + 2 * i : 10 + 2 * i], "little") for i in range(count)]
        return None


    def party_size(self) -> int:
        return self.read_symbol("gPlayerPartyCount")[0]

    def party_pokemon(self, index: int = 0) -> PartyPokemon:
        return parse_party_pokemon(self.read_symbol("gPlayerParty", index * PARTY_POKEMON_SIZE, PARTY_POKEMON_SIZE))

    def newest_party_pokemon(self) -> PartyPokemon:
        return self.party_pokemon(self.party_size() - 1)

    def enemy_pokemon(self, index: int = 0) -> PartyPokemon:
        return parse_party_pokemon(self.read_symbol("gEnemyParty", index * PARTY_POKEMON_SIZE, PARTY_POKEMON_SIZE))

    def enemy_pid(self) -> int:
        return int.from_bytes(self.read_symbol("gEnemyParty", 0, 4), "little")


    def save_block_address(self, number: int) -> int:
        if self.game.fixed_save_blocks:
            return self.symbol(f"gSaveBlock{number}")[0]
        pointer = int.from_bytes(self.read_symbol(f"gSaveBlock{number}Ptr"), "little")
        if pointer == 0:
            raise EmulatorError("The game has no save data in memory yet.")
        return pointer

    def save_block_1_address(self) -> int:
        return self.save_block_address(1)

    def read_save_block(self, number: int, offset: int, size: int) -> bytes | None:
        if self.game.fixed_save_blocks:
            return self.emulator.read_bytes(self.symbol(f"gSaveBlock{number}")[0] + offset, size)
        pointer = int.from_bytes(self.read_symbol(f"gSaveBlock{number}Ptr"), "little")
        if pointer == 0:
            return None
        return self.emulator.read_bytes(pointer + offset, size)

    def trainer_name(self) -> str | None:
        data = self.read_save_block(2, layout.PLAYER_NAME_OFFSET, 7)
        if data is None:
            return None
        letters = []
        for byte in data:
            if byte == 0xFF:
                break
            if 0xBB <= byte <= 0xD4:
                letters.append(chr(ord("A") + byte - 0xBB))
            elif 0xD5 <= byte <= 0xEE:
                letters.append(chr(ord("a") + byte - 0xD5))
            elif 0xA1 <= byte <= 0xAA:
                letters.append(str(byte - 0xA1))
            else:
                letters.append({0x00: " ", 0xAB: "!", 0xAC: "?", 0xAD: ".", 0xAE: "-"}.get(byte, "·"))
        return "".join(letters).strip() or None

    def trainer_ids(self) -> tuple[int, int] | None:
        data = self.read_save_block(2, layout.TRAINER_ID_OFFSET, 4)
        if data is None:
            return None
        return int.from_bytes(data[:2], "little"), int.from_bytes(data[2:4], "little")

    def player_is_female(self) -> bool:
        data = self.read_save_block(2, layout.PLAYER_GENDER_OFFSET, 1)
        return data is not None and data[0] == 1

    def map_group_and_number(self) -> tuple[int, int] | None:
        data = self.read_save_block(1, layout.MAP_GROUP_OFFSET, 2)
        return None if data is None else (data[0], data[1])

    def player_position(self) -> tuple[int, int] | None:
        data = self.read_save_block(1, layout.PLAYER_X_OFFSET, 4)
        if data is None:
            return None
        return int.from_bytes(data[:2], "little"), int.from_bytes(data[2:4], "little")

    def is_surfing(self) -> bool:
        return bool(self.read_symbol("gPlayerAvatar", 0, 1)[0] & (1 << 3))


    def get_var(self, variable: int) -> int | None:
        data = self.read_save_block(1, self.game.vars_offset + (variable - layout.VAR_BASE) * 2, 2)
        return None if data is None else int.from_bytes(data, "little")

    def get_flag(self, flag: int) -> bool:
        data = self.read_save_block(1, self.game.flags_offset + flag // 8, 1)
        return data is not None and bool(data[0] >> (flag % 8) & 1)

    def key_items(self) -> list[int]:
        data = self.read_save_block(1, self.game.key_items_offset, self.game.key_items_count * 4)
        if data is None:
            return []
        return [int.from_bytes(data[slot * 4 : slot * 4 + 2], "little") for slot in range(self.game.key_items_count)]


    def save_in_game(self, save_data: bytes = b"") -> None:
        from shiny.games.gen3 import savegame

        if self.in_overworld():
            savegame.align_save_counter(self.emulator, self, save_data)
        savegame.save_in_game(self.emulator, self)
