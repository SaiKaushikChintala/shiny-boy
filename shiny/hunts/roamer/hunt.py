from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.scan.engine import HUNT_SNAPSHOT_EVERY, Method1Hunt, ScriptFailed
from shiny.games.gen3 import layout
from shiny.games.gen3.inputs import run
from shiny.games.gen3.maps import map_grid, warps
from shiny.games.gen3.reader import Gen3Reader
from shiny.games.gen3.walking import face, find_path, walk_path
from shiny.hunts.base import NOT_OVERWORLD, Bot
from shiny.hunts.roamer.options import EMERALD_OPTIONS, OPTIONS

TELEVISION = 0x86
MULTICHOICE_TASK = "TASK_HANDLEMULTICHOICEINPUT"
SCENE_FRAMES = 6000
MAX_PRESS_FRAMES = 400
HOUSES = ((1, 0), (1, 2))
LITTLEROOT = (0, 9)
CELIO = (32, 0)
CELIO_STAND = (15, 7)


def read_roamer(game: Gen3Reader) -> PartyPokemon | None:
    data = game.read_save_block(1, game.game.roamer_offset, 0x14)
    ids = game.trainer_ids()
    if data is None or ids is None or not data[0x13] or not (data[8] or data[9]):
        return None
    return PartyPokemon(
        personality_value=int.from_bytes(data[4:8], "little"),
        trainer_id=ids[0],
        secret_id=ids[1],
        species=int.from_bytes(data[8:10], "little"),
        iv_word=int.from_bytes(data[0:4], "little"),
        checksum_is_valid=True,
    )


def tiles_below_television(game: Gen3Reader) -> list[tuple[int, int]]:
    group, number = game.map_group_and_number()
    grid = map_grid(game, group, number)
    below = []
    for index in range(grid.width * grid.height):
        if grid.behaviour(grid.block(index) & layout.BLOCK_METATILE_MASK) == TELEVISION:
            below.append((index % grid.width, index // grid.width + 1))
    return below


def enter_house(emu: EmulatorInterface, game: Gen3Reader) -> None:
    house = HOUSES[1] if game.player_is_female() else HOUSES[0]
    door = next((warp for warp in warps(game) if (warp["group"], warp["number"]) == house), None)
    way = None if door is None else find_path(game, (door["x"], door["y"] + 1))
    if way is None:
        raise ScriptFailed("There is no way to the door of your house. Stand in Littleroot Town, where you can walk to it.")
    walk_path(emu, game, way)
    for _ in range(120):
        run(emu, Button.UP)
        if game.map_group_and_number() == house:
            return
    raise ScriptFailed("Could not go in through the door of your house.")


def scene_to_choice(emu: EmulatorInterface, game: Gen3Reader, answer: int, log: Callable[[str], None]) -> list[int]:
    emu.start_recording()
    if game.map_group_and_number() == LITTLEROOT:
        try:
            enter_house(emu, game)
        except ScriptFailed:
            emu.stop_recording()
            raise
    for frame in range(SCENE_FRAMES):
        if MULTICHOICE_TASK in game.active_tasks():
            break
        run(emu, Button.A if frame % 10 == 0 else 0)
    else:
        emu.stop_recording()
        raise ScriptFailed("The TV scene with Mom did not come. Be after the Hall of Fame, with the English Emerald, outside your house.")
    run(emu, 0, 30)
    for _ in range(answer):
        run(emu, Button.DOWN, 2)
        run(emu, 0, 20)
    keys = emu.stop_recording()
    log(f"Mom's question is up after {len(keys):,} frames.")
    return keys


def scene_to_news(emu: EmulatorInterface, game: Gen3Reader, log: Callable[[str], None], celio: bool = False) -> list[int]:
    emu.start_recording()
    if celio:
        way = find_path(game, CELIO_STAND)
        if way is None:
            emu.stop_recording()
            raise ScriptFailed("There is no way to Celio. Stand in the Pokémon Center of One Island, where you can walk to him.")
        walk_path(emu, game, way)
    else:
        for tile in tiles_below_television(game):
            way = find_path(game, tile)
            if way is not None:
                walk_path(emu, game, way)
                break
        else:
            emu.stop_recording()
            raise ScriptFailed("Could not walk to the television. Be in your own house, with nobody in the way.")
    face(emu, Button.UP)
    walk_keys = emu.stop_recording()
    front = emu.get_state()
    pid = _roamer_pid(game)
    emu.start_recording()
    for frame in range(SCENE_FRAMES):
        run(emu, Button.A if frame % 10 == 0 else 0)
        if _roamer_pid(game) not in (None, pid):
            break
    else:
        emu.stop_recording()
        raise ScriptFailed("The roamer was not made by the talk. Be after the Hall of Fame (the news on in your own house; Celio after the Sapphire is back).")
    scene = emu.stop_recording()
    for back in (60, 90, 120, 40, 150, 200):
        stop = max(0, len(scene) - back)
        emu.set_state(front)
        for key in scene[:stop]:
            run(emu, key)
        run(emu, 0, 20)
        ready = emu.get_state()
        for frame in range(40):
            run(emu, Button.A if frame % 2 == 0 else 0)
            if _roamer_pid(game) not in (None, pid):
                break
        else:
            continue
        emu.set_state(ready)
        keys = walk_keys + scene[:stop] + [0] * 20
        log(f"The news is on the screen after {len(keys):,} frames.")
        return keys
    raise ScriptFailed("Could not find the place to wait at in the news.")


def _roamer_pid(game: Gen3Reader) -> int | None:
    roamer = read_roamer(game)
    return None if roamer is None else roamer.personality_value


class RoamerHunt(Method1Hunt):

    NO_POKEMON_MESSAGE = "No roamer was made at the last press."

    def _run_script(self) -> PartyPokemon:
        before = _roamer_pid(self.game)
        for frame in range(MAX_PRESS_FRAMES):
            run(self.emu, Button.A if frame % 2 == 0 else 0)
            roamer = read_roamer(self.game)
            if roamer is not None and roamer.personality_value != before:
                return roamer
        raise ScriptFailed("No roamer was made.")


class RoamerBot(Bot):

    def __init__(self, game_key: str = "emerald"):
        self.game_key = game_key
        self.frlg = game_key in ("firered", "leafgreen")
        self.options = EMERALD_OPTIONS if game_key == "emerald" else OPTIONS

    def goal(self, options):
        return f"a shiny {options['choice'].title()}" if options.get("choice") else "a shiny roamer"

    def target_species(self, game, options):
        return options["choice"] if options.get("choice") else None

    def result(self, game, plan=None):
        return read_roamer(game)

    def state_problem(self, game):
        if not game.in_overworld():
            return NOT_OVERWORLD
        where = game.map_group_and_number()
        if self.frlg:
            if where != CELIO:
                return "Stand in the Pokémon Center of One Island first (Celio's, after the Sapphire is back)."
        elif self.game_key == "emerald":
            if where != LITTLEROOT and where not in HOUSES:
                return "Be in Littleroot Town first, outside your own house (after the Hall of Fame)."
        elif where not in HOUSES:
            return "Be inside your own house in Littleroot Town first (after the Hall of Fame)."
        if read_roamer(game) is not None:
            return "A roaming Pokémon has been made in this save already. Load a save from before it."
        return None

    def hunt(self, emu, game, start_state, options, log):
        emu.set_state(start_state)
        if self.game_key == "emerald":
            answer = self.options.choices.index(options["choice"].title())
            prelude = scene_to_choice(emu, game, answer, log)
        else:
            prelude = scene_to_news(emu, game, log, celio=self.frlg)
        hunt = RoamerHunt(emu, game, emu.get_state(), options["nature"], log, HUNT_SNAPSHOT_EVERY)
        return self._hunt_and_plan(emu, game, start_state, hunt, options, prelude)
