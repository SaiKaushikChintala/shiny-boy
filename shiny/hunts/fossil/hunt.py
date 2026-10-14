from typing import Callable

from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.scan.engine import HUNT_SNAPSHOT_EVERY, ScriptFailed
from shiny.games.gen3.reader import Gen3Reader
from shiny.hunts.base import Bot
from shiny.hunts.fossil.options import OPTIONS
from shiny.hunts.gift.hunt import GiftHunt

VAR_FOSSIL_RESURRECTION_STATE = 0x40C4
VAR_WHICH_FOSSIL_REVIVED = 0x40C5
FOSSIL_READY = 2
FOSSILS = {1: "Lileep", 2: "Anorith"}

NOT_READY_MESSAGE = (
    "The fossil is not ready. Hand it to the researcher in the Devon Corporation (2nd floor), talk to another researcher "
    "in the room, then stand in front of the fossil researcher and try again."
)


def fossil_problem(game: Gen3Reader) -> str | None:
    if game.get_var(VAR_FOSSIL_RESURRECTION_STATE) != FOSSIL_READY:
        return NOT_READY_MESSAGE
    if game.party_size() >= 6:
        return "The party is full. Leave a free place for the new Pokémon."
    return None


class FossilHunt(GiftHunt):
    NO_POKEMON_MESSAGE = NOT_READY_MESSAGE

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
        problem = fossil_problem(self._game_at_start())
        if problem is not None:
            raise ScriptFailed(problem)

    def _game_at_start(self) -> Gen3Reader:
        self.emu.set_state(self.start_state)
        self.emu.run_frame()
        return self.game


class FossilBot(Bot):

    options = OPTIONS

    def target_species(self, game, options):
        return FOSSILS.get(game.get_var(VAR_WHICH_FOSSIL_REVIVED), "").lower() or None

    def state_problem(self, game):
        return fossil_problem(game)

    def hunt(self, emu, game, start_state, options, log):
        hunt = FossilHunt(emu, game, start_state, options["nature"], log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options)
