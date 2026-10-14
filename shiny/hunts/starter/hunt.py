from typing import Callable, Generator

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.scan.engine import HUNT_SNAPSHOT_EVERY, Method1Hunt, ScriptFailed
from shiny.games.gen3.reader import Gen3Reader
from shiny.hunts.base import NOT_OVERWORLD, Bot
from shiny.hunts.starter.options import OPTIONS

CHOOSE_STARTER_TASKS = {"ruby": "Task_StarterChoose2", "sapphire": "Task_StarterChoose2", "emerald": "Task_HandleStarterChooseInput"}

STARTERS = {
    "treecko": (277, 0),
    "torchic": (280, 1),
    "mudkip": (283, 2),
}

ROUTE_101 = (0, 16)


def starter_inputs(game: Gen3Reader, starter: str, max_frames: int = 3000) -> Generator[int, None, PartyPokemon]:
    species, target = STARTERS[starter]
    phase = "talk to the bag"
    last_keys = 0

    for _ in range(max_frames):
        keys = 0
        mash = Button.A if not (last_keys & Button.A) else 0

        selection = game.task_data(CHOOSE_STARTER_TASKS[game.key], 1)
        if phase == "talk to the bag":
            if selection is None:
                keys = mash
            else:
                phase = "choose"
        if phase == "choose":
            if selection is None:
                keys = 0
            elif selection[0] == target:
                phase = "confirm"
            else:
                direction = Button.RIGHT if selection[0] < target else Button.LEFT
                keys = direction if last_keys != direction else 0
        if phase == "confirm":
            keys = mash

        yield keys
        last_keys = keys

        if game.party_size() >= 1:
            pokemon = game.party_pokemon(0)
            if pokemon.species != species:
                raise ScriptFailed(f"Got {pokemon.species_name} instead of {starter.title()}.")
            return pokemon

    raise ScriptFailed(f"No starter after {max_frames} frames.")


def run_starter_script(emu: EmulatorInterface, game: Gen3Reader, starter: str, max_frames: int = 3000) -> PartyPokemon:
    inputs = starter_inputs(game, starter, max_frames)
    try:
        while True:
            emu.set_keys(next(inputs))
            emu.run_frame()
    except StopIteration as finished:
        return finished.value


class StarterHunt(Method1Hunt):
    NO_POKEMON_MESSAGE = (
        "No starter appeared. Stand right in front of Prof. Birch's bag, facing it, "
        "with an empty party, and try again."
    )

    def __init__(
        self,
        emu: EmulatorInterface,
        game: Gen3Reader,
        start_state: bytes,
        starter: str,
        nature: str | None = None,
        log: Callable[[str], None] = print,
        snapshot_every: int = HUNT_SNAPSHOT_EVERY,
    ):
        super().__init__(emu, game, start_state, nature, log, snapshot_every)
        self.starter = starter

    def _run_script(self) -> PartyPokemon:
        return run_starter_script(self.emu, self.game, self.starter)


class StarterBot(Bot):

    options = OPTIONS

    def goal(self, options):
        return f"a shiny {options['choice'].title()}"

    def target_species(self, game, options):
        return options["choice"]

    def state_problem(self, game):
        if not game.in_overworld():
            return NOT_OVERWORLD
        if game.party_size() != 0:
            return "You already have a Pokémon. Load a state in front of Birch's bag first."
        if game.map_group_and_number() != ROUTE_101:
            return "Stand in front of Prof. Birch's bag on Route 101 first."
        return None

    def hunt(self, emu, game, start_state, options, log):
        hunt = StarterHunt(emu, game, start_state, options["choice"], options["nature"], log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options)
