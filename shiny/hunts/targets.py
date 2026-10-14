from dataclasses import dataclass, replace

from shiny.core.pokemon.natures import NATURE_COUNT, NATURES
from shiny.core.pokemon.species import gen3_name
from shiny.core.rng import lcrng
from shiny.core.rng.method1 import method1_at, method1_iv_word, shiny_positions
from shiny.core.rng.method_h import shiny_wild_starts, wild_pid
from shiny.games.gen3.encounters import choose_slot

HIDDEN_POWER_TYPES = (
    "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost", "Steel",
    "Fire", "Water", "Grass", "Electric", "Psychic", "Ice", "Dragon", "Dark",
)

SPECIES = {
    "treecko": (("Overgrow", None), 31),
    "torchic": (("Blaze", None), 31),
    "mudkip": (("Torrent", None), 31),
    "lileep": (("Suction Cups", None), 31),
    "anorith": (("Battle Armor", None), 31),
}


@dataclass(frozen=True)
class Target:
    advance: int
    pid: int
    iv_word: int
    shiny: str
    nature: str
    ability: str
    ivs: tuple[int, int, int, int, int, int] | None
    hidden_power: str
    power: int | None
    gender: str
    species: str = "—"
    level: str = "—"
    reachable: bool | None = None

    @property
    def key(self) -> tuple[int, int]:
        return self.pid, self.iv_word


def describe(
    pid: int, iv_word: int, advance: int, trainer_id: int, secret_id: int, species: str | None, name: str = "—", level: str = "—"
) -> Target:
    hp, atk, defense, spe, spa, spd = (iv_word >> shift & 31 for shift in (0, 5, 10, 15, 20, 25))
    value = trainer_id ^ secret_id ^ (pid >> 16) ^ (pid & 0xFFFF)
    abilities, gender_threshold = SPECIES.get(species or "", ((None, None), None))
    slot = pid & 1
    ability_name = abilities[slot] or abilities[0]
    ability = f"{slot + 1}: {ability_name}" if ability_name else f"{slot + 1}"
    stats = (hp, atk, defense, spe, spa, spd)
    type_bits = sum((iv & 1) << index for index, iv in enumerate(stats))
    power_bits = sum((iv >> 1 & 1) << index for index, iv in enumerate(stats))
    gender = "—" if gender_threshold is None else ("F" if pid & 0xFF < gender_threshold else "M")
    return Target(
        advance=advance,
        pid=pid,
        iv_word=iv_word,
        shiny="Square" if value == 0 else "Star",
        nature=NATURES[pid % NATURE_COUNT],
        ability=ability,
        ivs=(hp, atk, defense, spa, spd, spe),
        hidden_power=HIDDEN_POWER_TYPES[type_bits * 15 // 63],
        power=power_bits * 40 // 63 + 30,
        gender=gender,
        species=name,
        level=level,
    )


def method1_targets(
    start_rng: int, trainer_id: int, secret_id: int, max_advance: int, species: str | None = None, nature: str | None = None, base: int = 0,
    level: str = "—",
) -> list[Target]:
    name = species.title() if species else "—"
    targets = []
    for advance in shiny_positions(start_rng, max_advance, trainer_id, secret_id, nature):
        pid, iv_word = method1_at(start_rng, advance)
        targets.append(describe(pid, iv_word, advance + base, trainer_id, secret_id, species, name, level))
    return targets


def mark_reachable(rows: list[Target], hunt, limit: int) -> list[Target]:
    numbers = lcrng.outputs(hunt.start_rng, int(limit * 1.3) + 600)
    marked = []
    for row in rows:
        if row.advance > limit:
            marked.append(row)
            continue
        marked.append(replace(row, reachable=hunt.hits(row.advance, row.pid, limit, numbers)))
    return marked


def wild_targets(
    start_rng: int, trainer_id: int, secret_id: int, max_advance: int, slots: list[tuple[int, int, int]], kind: str, nature: str | None = None,
    iv_pattern: tuple[int, int] = (0, 1),
) -> list[Target]:
    numbers = lcrng.outputs(start_rng, max_advance + 600)
    targets = []
    for start, pid in shiny_wild_starts(numbers, trainer_id, secret_id, 0, max_advance):
        if nature is not None and NATURES[pid % NATURE_COUNT] != nature:
            continue
        lowest, highest, species = slots[choose_slot(kind, numbers[start])]
        level = lowest + numbers[start + 1] % (highest - lowest + 1)
        _nature, _pid, end = wild_pid(numbers, start)
        first, second = iv_pattern
        iv_word = method1_iv_word(numbers[end + first], numbers[end + second]) if end + max(iv_pattern) < len(numbers) else 0
        targets.append(describe(pid, iv_word, start, trainer_id, secret_id, None, gen3_name(species), str(level)))
    return targets
