from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.scan.engine import HUNT_SNAPSHOT_EVERY, Method1Hunt, ScriptFailed
from shiny.games.gen3.reader import Gen3Reader
from shiny.hunts.base import WildBot
from shiny.hunts.static.options import OPTIONS
from shiny.hunts.wild.hunt import EncounterTry

STATIC_FRAMES = 1000
PRESSES = ((Button.A, True), (Button.UP, False))


class StaticHunt(Method1Hunt):

    NO_POKEMON_MESSAGE = "No battle started. Stand right in front of the Pokémon (or the tile that starts the fight), facing it."

    def __init__(
        self,
        emu: EmulatorInterface,
        game: Gen3Reader,
        start_state: bytes,
        nature: str | None = None,
        log: Callable[[str], None] = print,
        snapshot_every: int = HUNT_SNAPSHOT_EVERY,
    ):
        super().__init__(emu, game, start_state, nature, log, snapshot_every)
        self.finder = EncounterTry(emu, game)
        self.press = self._find_press(start_state)

    def _find_press(self, start_state: bytes) -> tuple[int, bool]:
        for key, pulse in PRESSES:
            self.emu.set_state(start_state)
            if self.finder.play(key, pulse, STATIC_FRAMES) is not None:
                return key, pulse
        raise ScriptFailed(self.NO_POKEMON_MESSAGE)

    def _run_script(self) -> PartyPokemon:
        pokemon = self.finder.play(self.press[0], self.press[1], STATIC_FRAMES)
        if pokemon is None:
            raise ScriptFailed("No battle started.")
        return pokemon


class StaticBot(WildBot):

    options = OPTIONS

    def hunt(self, emu, game, start_state, options, log):
        hunt = StaticHunt(emu, game, start_state, options["nature"], log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options)
