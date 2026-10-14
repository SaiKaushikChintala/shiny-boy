MASK = 0xFFFFFFFF
MULTIPLIER = 0x41C64E6D
INCREMENT = 0x6073


def next_state(state: int) -> int:
    return (state * MULTIPLIER + INCREMENT) & MASK


def _build_jump_table() -> list[tuple[int, int]]:
    table = [(MULTIPLIER, INCREMENT)]
    for _ in range(31):
        multiplier, increment = table[-1]
        table.append(((multiplier * multiplier) & MASK, (increment * (multiplier + 1)) & MASK))
    return table


_JUMP_TABLE = _build_jump_table()


def advance(state: int, steps: int) -> int:
    for bit in range(32):
        if (steps >> bit) & 1:
            multiplier, increment = _JUMP_TABLE[bit]
            state = (state * multiplier + increment) & MASK
    return state


def distance(start: int, end: int) -> int:
    steps = 0
    for bit in range(32):
        if start == end:
            break
        if (start ^ end) & (1 << bit):
            multiplier, increment = _JUMP_TABLE[bit]
            start = (start * multiplier + increment) & MASK
            steps += 1 << bit
    return steps


def outputs(state: int, count: int) -> list[int]:
    result = []
    for _ in range(count):
        state = (state * MULTIPLIER + INCREMENT) & MASK
        result.append(state >> 16)
    return result
