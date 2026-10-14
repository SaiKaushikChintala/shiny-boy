from shiny.core.emulator.interface import EmulatorError, EmulatorInterface
from shiny.games.gen1 import layout as gen1_layout
from shiny.games.gen1.reader import Gen1Reader
from shiny.games.gen2 import layout as gen2_layout
from shiny.games.gen2.reader import Gen2Reader
from shiny.games.gen3.reader import Gen3Reader


def open_reader(emulator) -> Gen3Reader | Gen1Reader | Gen2Reader | None:
    if emulator.is_gba:
        try:
            return Gen3Reader(emulator)
        except EmulatorError:
            return None
    title = emulator.title
    if title in gen1_layout.TITLES:
        return Gen1Reader(emulator, gen1_layout.TITLES[title])
    if title in gen2_layout.TITLES and emulator.code.endswith("E"):
        return Gen2Reader(emulator, gen2_layout.TITLES[title])
    return None


def reader_for_emulator(emulator: EmulatorInterface):
    reader = open_reader(emulator)
    if reader is None:
        raise EmulatorError("This is not one of the supported Pokémon games (the English Ruby, Sapphire, Emerald, FireRed, LeafGreen, Red, Blue, Yellow, Gold, Silver or Crystal).")
    return reader
