from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.species import gen1_name
from shiny.games.gameboy import GameBoyReader
from shiny.games.gen1 import layout


class Gen1Reader(GameBoyReader):
    generation = 1
    party = layout.PARTY
    battle_symbol = layout.BATTLE_SYMBOL
    tilemap_symbol = layout.TILEMAP_SYMBOL

    def __init__(self, emulator: EmulatorInterface, key: str):
        super().__init__(emulator, key)

    def species_name(self, species: int) -> str:
        return gen1_name(species)

    def map_group_and_number(self) -> tuple[int, int]:
        return 0, self.byte("wCurMap")
