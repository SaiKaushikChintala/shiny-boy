from shiny.games.gen3.reader import Gen3Reader

HEADER_SIZE = 20
HEADER_END = 0xFF

KINDS = {"land": (0, 12), "water": (1, 5), "rock": (2, 5), "fishing": (3, 10)}

LIMITS = {
    "land": (20, 40, 50, 60, 70, 80, 85, 90, 94, 98, 99, 100),
    "water": (60, 90, 95, 99, 100),
    "rock": (60, 90, 95, 99, 100),
    "old": (70, 100),
    "good": (60, 80, 100),
    "super": (40, 80, 95, 99, 100),
}
FIRST_SLOT = {"old": 0, "good": 2, "super": 5}
RODS = {"Old Rod": "old", "Good Rod": "good", "Super Rod": "super"}


def choose_slot(kind: str, number: int) -> int:
    roll = number % 100
    for index, limit in enumerate(LIMITS[kind]):
        if roll < limit:
            return FIRST_SLOT.get(kind, 0) + index
    return FIRST_SLOT.get(kind, 0) + len(LIMITS[kind]) - 1


def slots_for(game: Gen3Reader, kind: str) -> list[tuple[int, int, int]] | None:
    group, number = game.map_group_and_number()
    address, size = game.symbol("gWildMonHeaders")
    table = game.emulator.read_bytes(address, size)
    which, count = KINDS[kind]
    for start in range(0, len(table) - HEADER_SIZE + 1, HEADER_SIZE):
        header = table[start : start + HEADER_SIZE]
        if header[0] == HEADER_END:
            break
        if (header[0], header[1]) != (group, number):
            continue
        info = int.from_bytes(header[4 + which * 4 : 8 + which * 4], "little")
        if info == 0:
            return None
        slots_pointer = int.from_bytes(game.emulator.read_bytes(info + 4, 4), "little")
        data = game.emulator.read_bytes(slots_pointer, count * 4)
        return [(data[i * 4], data[i * 4 + 1], int.from_bytes(data[i * 4 + 2 : i * 4 + 4], "little")) for i in range(count)]
    return None
