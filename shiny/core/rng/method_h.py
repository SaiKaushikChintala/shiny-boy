from shiny.core.pokemon.natures import NATURE_COUNT
from shiny.core.rng.shiny_rule import SHINY_LIMIT


def wild_pid(numbers: list[int], start: int) -> tuple[int, int, int] | None:
    if start + 3 >= len(numbers):
        return None
    nature = numbers[start + 2] % NATURE_COUNT
    position = start + 3
    while position + 1 < len(numbers):
        pid = (numbers[position + 1] << 16) | numbers[position]
        if pid % NATURE_COUNT == nature:
            return nature, pid, position + 2
        position += 2
    return None


def shiny_wild_starts(numbers: list[int], trainer_id: int, secret_id: int, first: int = 0, last: int | None = None):
    shiny_key = trainer_id ^ secret_id
    last = len(numbers) if last is None else last
    for start in range(first, last):
        found = wild_pid(numbers, start)
        if found is None:
            return
        _nature, pid, _end = found
        if (shiny_key ^ (pid >> 16) ^ (pid & 0xFFFF)) < SHINY_LIMIT:
            yield start, pid
