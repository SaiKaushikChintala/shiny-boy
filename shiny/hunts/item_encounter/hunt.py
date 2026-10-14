from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.scan.engine import HUNT_SNAPSHOT_EVERY, Method1Hunt, ScriptFailed
from shiny.games.gen3.bag import open_key_item_menu
from shiny.games.gen3.reader import Gen3Reader
from shiny.hunts.base import WildBot
from shiny.hunts.item_encounter.options import OPTIONS
from shiny.hunts.wild.hunt import EncounterTry

WAILMER_PAIL = 268
USE_FRAMES = 1500


class PailHunt(Method1Hunt):

    NO_POKEMON_MESSAGE = "Nothing appeared when the Wailmer Pail was used. Stand right in front of Sudowoodo, facing it, with the Wailmer Pail in the bag."

    def __init__(self, emu: EmulatorInterface, game: Gen3Reader, start_state: bytes, nature: str | None, log, snapshot_every: int = HUNT_SNAPSHOT_EVERY):
        super().__init__(emu, game, start_state, nature, log, snapshot_every)
        self.finder = EncounterTry(emu, game)

    def _run_script(self) -> PartyPokemon:
        pokemon = self.finder.play(Button.A, True, USE_FRAMES)
        if pokemon is None:
            raise ScriptFailed(self.NO_POKEMON_MESSAGE)
        return pokemon


class SudowoodoBot(WildBot):

    options = OPTIONS

    def hunt(self, emu, game, start_state, options, log):
        emu.set_state(start_state)
        emu.start_recording()
        menu = open_key_item_menu(emu, game, WAILMER_PAIL, "Wailmer Pail")
        prelude = emu.stop_recording()
        hunt = PailHunt(emu, game, menu, options["nature"], log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options, prelude)
