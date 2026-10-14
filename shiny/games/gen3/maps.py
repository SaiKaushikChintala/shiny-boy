from dataclasses import dataclass
from typing import Callable

from shiny.games.gen3 import layout
from shiny.games.gen3.reader import Gen3Reader


@dataclass
class MapGrid:
    width: int
    height: int
    block: Callable[[int], int]
    behaviour: Callable[[int], int]


def map_grid(game: Gen3Reader, group: int, number: int) -> MapGrid:
    read = game.emulator.read_bytes
    groups = game.symbol("gMapGroups")[0]
    table = int.from_bytes(read(groups + group * 4, 4), "little")
    header = int.from_bytes(read(table + number * 4, 4), "little")
    layout_address = int.from_bytes(read(header, 4), "little")
    width, height = (int.from_bytes(read(layout_address + offset, 4), "little") for offset in (0, 4))
    data = int.from_bytes(read(layout_address + 12, 4), "little")
    tilesets = [int.from_bytes(read(layout_address + offset, 4), "little") for offset in (16, 20)]
    kind = game.game
    attributes = [int.from_bytes(read(tileset + kind.tile_attribute_offset, 4), "little") for tileset in tilesets]
    grid = read(data, width * height * 2)
    cache: dict[int, int] = {}

    def block(index: int) -> int:
        return int.from_bytes(grid[index * 2 : index * 2 + 2], "little")

    def behaviour(metatile: int) -> int:
        if metatile not in cache:
            primary = metatile < kind.primary_metatiles
            address = attributes[0 if primary else 1] + (metatile if primary else metatile - kind.primary_metatiles) * kind.tile_attribute_size
            cache[metatile] = int.from_bytes(read(address, kind.tile_attribute_size), "little") & kind.behaviour_mask
        return cache[metatile]

    return MapGrid(width, height, block, behaviour)


def _walkable_tiles(game: Gen3Reader, group: int, number: int, wanted: Callable[[int], bool]) -> tuple[int, int, set[tuple[int, int]]]:
    grid = map_grid(game, group, number)
    tiles = set()
    for index in range(grid.width * grid.height):
        value = grid.block(index)
        if value & layout.BLOCK_BLOCKED_MASK:
            continue
        if wanted(grid.behaviour(value & layout.BLOCK_METATILE_MASK)):
            tiles.add((index % grid.width, index // grid.width))
    return grid.width, grid.height, tiles


def grass_tiles(game: Gen3Reader, group: int, number: int) -> tuple[int, int, set[tuple[int, int]]]:
    if game.game.grass_behaviours is not None:
        return _walkable_tiles(game, group, number, game.game.grass_behaviours.__contains__)
    bits = game.read_symbol("sTileBitAttributes")
    return _walkable_tiles(game, group, number, lambda behaviour: behaviour < len(bits) and bits[behaviour] & 3 == 1)


def water_tiles(game: Gen3Reader, group: int, number: int) -> tuple[int, int, set[tuple[int, int]]]:
    if game.game.water_behaviours is not None:
        return _walkable_tiles(game, group, number, game.game.water_behaviours.__contains__)
    bits = game.read_symbol("sTileBitAttributes")
    return _walkable_tiles(game, group, number, lambda behaviour: behaviour < len(bits) and bool(bits[behaviour] & 2))


def warps(game: Gen3Reader) -> list[dict]:
    header = game.read_symbol("gMapHeader")
    events = int.from_bytes(header[4:8], "little")
    if events == 0:
        return []
    counts = game.emulator.read_bytes(events, 4)
    warp_count = counts[1]
    table = int.from_bytes(game.emulator.read_bytes(events + 8, 4), "little")
    found = []
    for index in range(warp_count):
        entry = game.emulator.read_bytes(table + index * 8, 8)
        found.append(
            {
                "x": int.from_bytes(entry[0:2], "little", signed=True),
                "y": int.from_bytes(entry[2:4], "little", signed=True),
                "number": entry[6],
                "group": entry[7],
            }
        )
    return found


def object_events(game: Gen3Reader) -> list[dict]:
    data = game.read_symbol("gObjectEvents")
    found = []
    for index in range(layout.OBJECT_EVENT_COUNT):
        entry = data[index * layout.OBJECT_EVENT_SIZE : (index + 1) * layout.OBJECT_EVENT_SIZE]
        if not entry[0] & 1:
            continue
        x = int.from_bytes(entry[0x14:0x16], "little", signed=True) - layout.MAP_OFFSET
        y = int.from_bytes(entry[0x16:0x18], "little", signed=True) - layout.MAP_OFFSET
        found.append({"index": index, "local_id": entry[0x0C], "graphics": entry[0x09], "x": x, "y": y})
    return found
