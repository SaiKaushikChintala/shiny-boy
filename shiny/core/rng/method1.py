from shiny.core.pokemon.model import PartyPokemon
from shiny.core.pokemon.natures import NATURE_COUNT, NATURES
from shiny.core.rng import lcrng
from shiny.core.rng.shiny_rule import SHINY_LIMIT


def method1_pid(low_output: int, high_output: int) -> int:
    return (high_output << 16) | low_output


def method1_iv_word(iv1_output: int, iv2_output: int) -> int:
    return (iv1_output & 0x7FFF) | ((iv2_output & 0x7FFF) << 15)


def method1_at(start_rng: int, advance: int) -> tuple[int, int]:
    low, high, iv1, iv2 = lcrng.outputs(lcrng.advance(start_rng, advance), 4)
    return method1_pid(low, high), method1_iv_word(iv1, iv2)


def shiny_positions(start_rng: int, max_position: int, trainer_id: int, secret_id: int, nature: str | None = None):
    shiny_key = trainer_id ^ secret_id
    wanted_nature = None if nature is None else NATURES.index(nature)
    multiplier, increment, mask = lcrng.MULTIPLIER, lcrng.INCREMENT, lcrng.MASK

    state = start_rng
    window = []
    for _ in range(3):
        state = (state * multiplier + increment) & mask
        window.append(state >> 16)
    low, high, following = window

    for position in range(max_position + 1):
        if (shiny_key ^ low ^ high) < SHINY_LIMIT and (wanted_nature is None or (low | (high << 16)) % NATURE_COUNT == wanted_nature):
            yield position
        low, high = high, following
        state = (state * multiplier + increment) & mask
        following = state >> 16


def locate_generation(start_rng: int, pokemon: PartyPokemon, search_from: int, search_to: int) -> int | None:
    low = pokemon.personality_value & 0xFFFF
    high = pokemon.personality_value >> 16
    search_from = max(0, search_from)
    numbers = lcrng.outputs(lcrng.advance(start_rng, search_from), search_to - search_from + 4)
    for index in range(len(numbers) - 3):
        if (
            numbers[index] == low
            and numbers[index + 1] == high
            and method1_iv_word(numbers[index + 2], numbers[index + 3]) == pokemon.iv_word
        ):
            return search_from + index
    for index in range(len(numbers) - 1):
        if numbers[index] == low and numbers[index + 1] == high:
            return search_from + index
    return None
