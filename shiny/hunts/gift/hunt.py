from typing import Generator

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.scan.engine import HUNT_SNAPSHOT_EVERY, Method1Hunt, ScriptFailed
from shiny.games.gen3.inputs import run
from shiny.games.gen3.reader import Gen3Reader
from shiny.hunts.base import NOT_OVERWORLD, Bot
from shiny.hunts.gift.options import OPTIONS


def gift_inputs(game: Gen3Reader, max_frames: int = 15000) -> Generator[int, None, PartyPokemon]:
    party_size = game.party_size()
    last_keys = 0
    for _ in range(max_frames):
        keys = Button.A if not (last_keys & Button.A) else 0
        yield keys
        last_keys = keys
        if game.party_size() > party_size:
            return game.newest_party_pokemon()
    raise ScriptFailed(f"No Pokémon after {max_frames} frames.")


def run_inputs(emu: EmulatorInterface, inputs: Generator[int, None, PartyPokemon]) -> tuple[PartyPokemon, int]:
    frames = 0
    try:
        while True:
            emu.set_keys(next(inputs))
            emu.run_frame()
            frames += 1
    except StopIteration as finished:
        return finished.value, frames


STEADY_SPREAD = 3
LATER_STARTS = (60, 120, 240, 480, 900, 1500)


class GiftHunt(Method1Hunt):

    NO_POKEMON_MESSAGE = "No Pokémon was given. Stand in front of whoever gives it and try again."

    def _run_script(self) -> PartyPokemon:
        return run_inputs(self.emu, gift_inputs(self.game))[0]


class GiftBot(Bot):

    options = OPTIONS

    def state_problem(self, game):
        if not game.in_overworld():
            return NOT_OVERWORLD
        if game.party_size() >= 6:
            return "The party is full. Leave a free place for the new Pokémon."
        return None

    @staticmethod
    def _steady(hunt: GiftHunt) -> bool:
        try:
            hunt.calibrate()
        except ScriptFailed:
            return False
        if max(hunt.measured) - min(hunt.measured) <= STEADY_SPREAD:
            return True
        middle = hunt.offset
        return sum(abs(value - middle) <= 1 for value in hunt.measured) >= len(hunt.measured) - 1

    def _later_start(self, emu, game, start_state, options, log) -> tuple[GiftHunt, list[int]]:
        emu.set_state(start_state)
        emu.start_recording()
        run_inputs(emu, gift_inputs(game))
        keys = emu.stop_recording()
        for back in LATER_STARTS:
            if len(keys) - back <= 0:
                break
            emu.set_state(start_state)
            for key in keys[: len(keys) - back]:
                run(emu, key)
            hunt = GiftHunt(emu, game, emu.get_state(), options["nature"], log, HUNT_SNAPSHOT_EVERY)
            if self._steady(hunt):
                log(f"The wait goes {back} frames before the Pokémon is given (it is not steady at the start of the scene).")
                return hunt, keys[: len(keys) - back]
        raise ScriptFailed("The random numbers of this scene change from try to try, so no wait could be found.")

    def hunt(self, emu, game, start_state, options, log):
        hunt = GiftHunt(emu, game, start_state, options["nature"], log, HUNT_SNAPSHOT_EVERY)
        prelude: list[int] = []
        if self._steady(hunt):
            hunt.attempts_made = 0
        else:
            hunt, prelude = self._later_start(emu, game, start_state, options, log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options, prelude)
