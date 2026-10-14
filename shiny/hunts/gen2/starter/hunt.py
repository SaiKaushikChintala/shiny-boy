from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.scan.engine import ScriptFailed
from shiny.hunts.gen2.starter.options import OPTIONS
from shiny.hunts.timer_hunt import TimerBot, TimerHunt

STARTERS = {
    "cyndaquil": (Button.LEFT, 155),
    "totodile": (None, 158),
    "chikorita": (Button.RIGHT, 152),
}
STEP_TRIES = 120


class Gen2StarterHunt(TimerHunt):
    NO_POKEMON_MESSAGE = "No starter was given. Stand in front of the middle ball in Elm's lab, facing it, with an empty party."

    def __init__(self, emu: EmulatorInterface, game, start_state: bytes, options: dict, log: Callable[[str], None] = print):
        self.side_key, self.species = STARTERS[options["choice"]]
        super().__init__(emu, game, start_state, options, log)

    def prepare(self) -> None:
        if self.side_key is None:
            return
        start_x = self.game.player_position()[0]
        for _ in range(STEP_TRIES):
            self._run(self.side_key, 1)
            if self.game.player_position()[0] != start_x:
                break
        else:
            raise ScriptFailed("The player did not move: is there something in the way?")
        self._run(0, 9)
        self._run(Button.UP, 3)
        self._run(0, 1)


class Gen2StarterBot(TimerBot):

    options = OPTIONS

    def state_problem(self, game):
        if game.in_battle():
            return "Be in the overworld first (not in a battle)."
        if game.party_size() != 0:
            return "You already have a Pokémon. Load a state in front of the starter first."
        return None

    def goal(self, options):
        return f"a shiny {options['choice'].title()}"

    def hunt(self, emu, game, start_state, options, log):
        return self._hunt_timer(emu, game, start_state, Gen2StarterHunt(emu, game, start_state, options, log), options)
