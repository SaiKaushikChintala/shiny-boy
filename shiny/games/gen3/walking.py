from collections import deque

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.scan.engine import ScriptFailed
from shiny.games.gen3 import layout
from shiny.games.gen3.inputs import run
from shiny.games.gen3.maps import grass_tiles, map_grid, object_events
from shiny.games.gen3.reader import Gen3Reader

MAX_STEP_FRAMES = 40
AFTER_STEP_FRAMES = 18
FACE_FRAMES = 6

DIRECTIONS = ((Button.UP, 0, -1), (Button.DOWN, 0, 1), (Button.LEFT, -1, 0), (Button.RIGHT, 1, 0))
OPPOSITE = {Button.UP: Button.DOWN, Button.DOWN: Button.UP, Button.LEFT: Button.RIGHT, Button.RIGHT: Button.LEFT}


def take_step(emu: EmulatorInterface, game: Gen3Reader, key: int) -> bool:
    start = game.player_position()
    moved = False
    for _ in range(MAX_STEP_FRAMES):
        run(emu, key)
        if game.player_position() != start:
            moved = True
            break
    run(emu, 0, AFTER_STEP_FRAMES)
    return moved


def face(emu: EmulatorInterface, key: int) -> None:
    run(emu, key, FACE_FRAMES)
    run(emu, 0, 30)


def free_tiles(game: Gen3Reader) -> set[tuple[int, int]]:
    group, number = game.map_group_and_number()
    grid = map_grid(game, group, number)
    _width, _height, grass = grass_tiles(game, group, number)
    people = {(person["x"], person["y"]) for person in object_events(game) if person["index"] != 0}
    tiles = set()
    for index in range(grid.width * grid.height):
        tile = (index % grid.width, index // grid.width)
        if not grid.block(index) & layout.BLOCK_BLOCKED_MASK and tile not in grass and tile not in people:
            tiles.add(tile)
    return tiles


def find_path(game: Gen3Reader, goal: tuple[int, int]) -> list[int] | None:
    start = game.player_position()
    tiles = free_tiles(game) | {start}
    came_from: dict[tuple[int, int], tuple[tuple[int, int], int]] = {}
    queue = deque([start])
    seen = {start}
    while queue:
        here = queue.popleft()
        if here == goal:
            keys = []
            while here != start:
                here, key = came_from[here]
                keys.append(key)
            return keys[::-1]
        for key, dx, dy in DIRECTIONS:
            there = (here[0] + dx, here[1] + dy)
            if there in tiles and there not in seen:
                seen.add(there)
                came_from[there] = (here, key)
                queue.append(there)
    return None


def walk_path(emu: EmulatorInterface, game: Gen3Reader, keys: list[int]) -> None:
    for key in keys:
        if not take_step(emu, game, key):
            raise ScriptFailed("Something is in the way (a person, or a wall). Try again from a place with free ground around.")


def step_pair(game: Gen3Reader) -> tuple[int, int] | None:
    x, y = game.player_position()
    tiles = free_tiles(game)
    for key, dx, dy in DIRECTIONS:
        if (x + dx, y + dy) in tiles:
            return key, OPPOSITE[key]
    return None
