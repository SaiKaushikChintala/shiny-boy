from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.hunts.gen1.starter.options import OPTIONS, OPTIONS_YELLOW
from shiny.hunts.timer_hunt import TimerBot, TimerHunt

SPECIES = {"bulbasaur": 0x99, "charmander": 0xB0, "squirtle": 0xB1}
PIKACHU = 0x54
YELLOW_WALK = (Button.DOWN, Button.RIGHT, Button.RIGHT)
EMPTY_PARTY = "You already have a Pokémon. Load a state in front of the starter first."


class Gen1StarterHunt(TimerHunt):

    A_FRAMES_ON = 2
    A_PERIOD = 25
    GIVE_TIMEOUT = 900
    BASELINE_TIMEOUT = 6000
    NO_POKEMON_MESSAGE = "No starter was given. Stand in front of the ball of the starter in Oak's lab, facing it, with an empty party."

    def __init__(self, emu: EmulatorInterface, game, start_state: bytes, options: dict, log: Callable[[str], None] = print):
        if options.get("choice"):
            self.species = SPECIES[options["choice"]]
        super().__init__(emu, game, start_state, options, log)

    def _given(self) -> bool:
        return self.game.party_pokemon_made(0)

    def _a_key(self, frame: int) -> int:
        if self.game.party_size() != 0:
            return Button.B if frame % self.A_PERIOD < self.A_FRAMES_ON else 0
        return super()._a_key(frame)


class YellowPikachuHunt(Gen1StarterHunt):

    GIVE_TIMEOUT = 600
    species = PIKACHU
    NO_POKEMON_MESSAGE = "No Pikachu was given. Stand next to the table with the ball in Oak's lab, before Oak has said it is yours."

    def _tap(self, key: int, frames_after: int) -> None:
        self._run(key, 4)
        self._run(0, frames_after)

    def prepare(self) -> None:
        self._tap(Button.A, 120)
        self._tap(Button.A, 60)
        for key in YELLOW_WALK:
            self._tap(key, 20)
        self._tap(Button.UP, 20)


class Gen1StarterBot(TimerBot):

    options = OPTIONS

    def state_problem(self, game):
        if game.in_battle():
            return "Be in the overworld first (not in a battle)."
        return EMPTY_PARTY if game.party_size() != 0 else None

    def goal(self, options):
        return f"a {options['choice'].title()} with shiny DVs"

    def hunt(self, emu, game, start_state, options, log):
        return self._hunt_timer(emu, game, start_state, Gen1StarterHunt(emu, game, start_state, options, log), options)


class YellowPikachuBot(Gen1StarterBot):

    options = OPTIONS_YELLOW

    def goal(self, options):
        return "a Pikachu with shiny DVs"

    def hunt(self, emu, game, start_state, options, log):
        return self._hunt_timer(emu, game, start_state, YellowPikachuHunt(emu, game, start_state, options, log), options)
