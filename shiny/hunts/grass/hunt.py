from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.scan.engine import HUNT_SNAPSHOT_EVERY, ScriptFailed
from shiny.games.gen3.encounters import slots_for
from shiny.games.gen3.inputs import run, tap
from shiny.games.gen3.maps import grass_tiles, water_tiles
from shiny.games.gen3.reader import Gen3Reader
from shiny.games.gen3.walking import OPPOSITE
from shiny.hunts.base import WildBot
from shiny.hunts.grass.options import OPTIONS
from shiny.hunts.wild.hunt import EncounterTry, WildHunt

WALK_FRAMES = 56
HUNT_STEPS = 3
PRE_STEPS = 5
ROW_LENGTH = PRE_STEPS + HUNT_STEPS
FRLG_ROW_LENGTH = 2
GRASS_MAX_DELAY = 1_500_000
FLEE_ATTEMPTS = 20
BATTLE_TASKS = {"TASK_BATTLESTART", "TASK_BATTLETRANSITION"}


def measure_pre_steps(emu: EmulatorInterface, game: Gen3Reader, arrival: bytes, key: int, tries: int = 8) -> int:
    first = []
    for wait in range(tries):
        emu.set_state(arrival)
        run(emu, 0, wait)
        before = game.enemy_pid()
        steps, last = 0, game.player_position()
        met = None
        for _ in range(16 * 40):
            run(emu, OPPOSITE[key] if steps % 2 else key)
            if game.player_position() != last:
                steps, last = steps + 1, game.player_position()
            if game.enemy_pid() not in (0, before):
                met = steps
                break
        first.append(met if met is not None else 40)
    return max(2, min(first) - 1)


def meet_and_flee(emu: EmulatorInterface, game: Gen3Reader, key: int, log: Callable[[str], None] = print) -> list[int]:
    emu.start_recording()
    before = game.enemy_pid()
    steps, last = 0, game.player_position()
    for _ in range(16 * 60):
        if game.active_tasks() & BATTLE_TASKS or not game.in_overworld():
            break
        run(emu, OPPOSITE[key] if steps % 2 else key)
        if game.player_position() != last:
            steps, last = steps + 1, game.player_position()
    else:
        emu.stop_recording()
        raise ScriptFailed("No Pokémon came in the grass. Stand somewhere with tall grass (or water to surf on) and try again.")
    for _ in range(FLEE_ATTEMPTS):
        if game.in_overworld() and not game.active_tasks() & BATTLE_TASKS and game.enemy_pid() != before:
            break
        tap(emu, Button.A, 40)
        tap(emu, Button.A, 40)
        tap(emu, Button.RIGHT, 20)
        tap(emu, Button.DOWN, 20)
        tap(emu, Button.A, 90)
        for _ in range(6):
            tap(emu, Button.A, 30)
            if game.in_overworld():
                break
    else:
        emu.stop_recording()
        raise ScriptFailed("Could not run away from the wild Pokémon.")
    run(emu, 0, 120)
    keys = emu.stop_recording()
    log(f"A wild Pokémon came after {steps} steps and the player ran away: the step counter of the encounters is at 0.")
    return keys


def step_into_grass(emu: EmulatorInterface, game: Gen3Reader, arrival: bytes, key: int, log: Callable[[str], None] = print) -> tuple[bytes, list[int]]:
    back_and_forth = game.game.measured_pre_steps
    needed = measure_pre_steps(emu, game, arrival, key) if back_and_forth else PRE_STEPS
    for wait in range(120):
        emu.set_state(arrival)
        emu.start_recording()
        run(emu, 0, wait)
        steps, last = 0, game.player_position()
        for _ in range(needed * 40):
            run(emu, OPPOSITE[key] if back_and_forth and steps % 2 else key)
            if game.player_position() != last:
                steps, last = steps + 1, game.player_position()
                if steps == needed:
                    break
        run(emu, 0, 40)
        keys = emu.stop_recording()
        if steps == needed and game.in_overworld() and not game.active_tasks() & BATTLE_TASKS:
            log(f"Took {steps} steps into the grass (after waiting {wait} frames).")
            return emu.get_state(), keys
    raise ScriptFailed("Could not walk in the grass without meeting a Pokémon.")


class WalkTry(EncounterTry):

    def __init__(self, emu: EmulatorInterface, game: Gen3Reader, direction: int):
        super().__init__(emu, game)
        self.direction = direction

    def play(self, key: int = 0, pulse: bool = False, max_frames: int = WALK_FRAMES) -> PartyPokemon | None:
        return super().play(self.direction, False, WALK_FRAMES)


def row_meets_pokemon(emu: EmulatorInterface, game: Gen3Reader, state: bytes, direction: int, tries: int = 160) -> bool:
    finder = WalkTry(emu, game, direction)
    for wait in range(tries):
        emu.set_state(state)
        run(emu, 0, wait)
        if finder.play() is not None:
            return True
    return False


class WalkHunt(WildHunt):

    OFFSETS = (18, 35, 52)
    OFFSET_WINDOW = (1, 70)
    CALIBRATION_WAITS = range(100, 220)
    TRY_CLASS = WalkTry

    def __init__(
        self,
        emu: EmulatorInterface,
        game: Gen3Reader,
        start_state: bytes,
        direction: int,
        nature: str | None = None,
        log: Callable[[str], None] = print,
        snapshot_every: int = HUNT_SNAPSHOT_EVERY,
    ):
        self.direction = direction
        super().__init__(emu, game, start_state, nature, log, snapshot_every)

    def _make_finder(self) -> WalkTry:
        return WalkTry(self.emu, self.game, self.direction)


class GrassBot(WildBot):

    options = OPTIONS

    @staticmethod
    def _row(game: Gen3Reader, surfing: bool) -> tuple[int, int]:
        group, number = game.map_group_and_number()
        _width, _height, tiles = water_tiles(game, group, number) if surfing else grass_tiles(game, group, number)
        x, y = game.player_position()
        best = (Button.DOWN, 0)
        for dx, dy, key in ((0, 1, Button.DOWN), (1, 0, Button.RIGHT), (0, -1, Button.UP), (-1, 0, Button.LEFT)):
            length = 0
            while (x + dx * (length + 1), y + dy * (length + 1)) in tiles:
                length += 1
            if length > best[1]:
                best = (key, length)
        return best

    def state_problem(self, game):
        problem = super().state_problem(game)
        if problem:
            return problem
        surfing = game.is_surfing()
        _key, length = self._row(game, surfing)
        needed = FRLG_ROW_LENGTH if game.game.measured_pre_steps else ROW_LENGTH
        if length < needed:
            return f"Stand at the start of a straight row of {'water' if surfing else 'tall grass'} (at least {needed} tiles long) and face along it."
        return None

    def limit(self, options):
        return super().limit(options) if options.get("targets") else GRASS_MAX_DELAY

    def _step_in(self, emu, game, start_state, log):
        emu.set_state(start_state)
        surfing = game.is_surfing()
        key, length = self._row(game, surfing)
        log(f"Stepping along a row of {length} tiles.")
        flee_keys = []
        arrival = start_state
        if game.game.measured_pre_steps:
            flee_keys = meet_and_flee(emu, game, key, log)
            arrival = emu.get_state()
        step_state, step_keys = step_into_grass(emu, game, arrival, key, log)
        step_keys = flee_keys + step_keys
        if not row_meets_pokemon(emu, game, step_state, key):
            raise ScriptFailed("No Pokémon can be met on this row: stand somewhere else in the grass (or water).")
        return step_state, step_keys, key, surfing

    def list_targets(self, emu, game, start_state, options, max_advance, log):
        step_state, _keys, key, surfing = self._step_in(emu, game, start_state, log)
        kind = "water" if surfing else "land"
        slots = slots_for(game, kind)
        if slots is None:
            raise ScriptFailed(f"There are no {'surfing' if surfing else 'grass'} encounters on this map.")
        hunt = WalkHunt(emu, game, step_state, key, options["nature"], log)
        return self._wild_rows(hunt, slots, kind, options, max_advance)

    def hunt(self, emu, game, start_state, options, log):
        step_state, step_keys, key, _surfing = self._step_in(emu, game, start_state, log)
        hunt = WalkHunt(emu, game, step_state, key, options["nature"], log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options, step_keys)
