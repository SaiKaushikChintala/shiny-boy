from dataclasses import dataclass, replace
from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PARTY_POKEMON_SIZE, PartyPokemon, parse_party_pokemon
from shiny.core.pokemon.natures import NATURE_COUNT, NATURES
from shiny.core.rng import lcrng
from shiny.core.rng.shiny_rule import is_shiny, shiny_value
from shiny.core.scan.engine import ScriptFailed
from shiny.core.scan.wait_table import WaitTable
from shiny.games.gen3.inputs import run
from shiny.games.gen3.reader import Gen3Reader
from shiny.games.gen3.walking import face, find_path, step_pair, take_step, walk_path
from shiny.hunts.base import NOT_OVERWORLD, Bot
from shiny.hunts.breeding.options import OPTIONS, RUBY_SAPPHIRE_OPTIONS
from shiny.hunts.plan import compress, play_keys
from shiny.hunts.targets import Target

SECOND_MON_STEPS = 0x114
READY_STEP_COUNT = 0xFE
OFFSPRING_PERSONALITY = 0x118
BOX_MON_SIZE = 80
MAX_WALK_STEPS = 300
CALIBRATION_WAITS = 90
MIN_IV_TOTAL = 150
MAX_PID_WAIT = 60000
MAX_IV_WAIT = 20000
EMERALD_AVAILABLE_1 = (0, 1, 2, 5, 3, 4)
EMERALD_AVAILABLE_2 = (1, 2, 5, 3, 4)
EMERALD_AVAILABLE_3 = (1, 5, 3, 4)
RS_ORDER = (0, 1, 2, 5, 3, 4)
RS_VARIANTS = ((1, 0, 1), (0, 1, 1), (1, 0, 2), (0, 0, 2))
MAX_FIND_EGG_WAIT = 400


def daycare_address(game: Gen3Reader) -> int:
    return game.save_block_1_address() + game.game.daycare_offset


def offspring_personality(game: Gen3Reader, emu: EmulatorInterface) -> int:
    return int.from_bytes(emu.read_bytes(daycare_address(game) + OFFSPRING_PERSONALITY, 2 if game.game.split_egg_pid else 4), "little")


def daycare_mons(game: Gen3Reader, emu: EmulatorInterface) -> list[PartyPokemon | None]:
    base = daycare_address(game)
    result = []
    for slot in range(2):
        box = emu.read_bytes(base + slot * game.game.daycare_mon_size, BOX_MON_SIZE)
        mon = parse_party_pokemon(box + bytes(PARTY_POKEMON_SIZE - BOX_MON_SIZE))
        result.append(mon if mon.checksum_is_valid and mon.species else None)
    return result


def day_care_steps(game: Gen3Reader, emu: EmulatorInterface) -> int:
    return int.from_bytes(emu.read_bytes(daycare_address(game) + SECOND_MON_STEPS, 4), "little")


def breeding_problem(game: Gen3Reader) -> str | None:
    if not game.in_overworld():
        return NOT_OVERWORLD
    if game.map_group_and_number() != game.game.daycare_map:
        return "Stand near the Day Care man first (on Route 117; on Four Island in FireRed and LeafGreen)."
    if not all(daycare_mons(game, game.emulator)):
        return "Leave two compatible Pokémon in the Day Care (one of them a Ditto is the easiest), then come out and stand near the Day Care man."
    if game.get_flag(game.game.pending_egg_flag):
        return "The Day Care already has an egg waiting. Take it first."
    if game.party_size() >= 6:
        return "The party is full. Leave a free place for the egg."
    if step_pair(game) is None:
        return "There is no free ground next to you (without tall grass) to walk back and forth on: stand somewhere else."
    if find_path(game, (game.game.daycare_man[0], game.game.daycare_man[1] + 1)) is None:
        return "There is no way from here to the Day Care man. Stand where you can walk to him."
    return None


def _top16(seed: int) -> int:
    return ((seed * lcrng.MULTIPLIER + lcrng.INCREMENT) & lcrng.MASK) >> 16


@dataclass
class EggModel:

    table: WaitTable
    frame_offset: int
    shifts: list[int]


def calibrate_egg_pid(emu: EmulatorInterface, game: Gen3Reader, state: bytes, step_key: int, log: Callable[[str], None]) -> EggModel:
    table = WaitTable(emu, game.rng_address, state)
    table.extend_to(CALIBRATION_WAITS)
    outputs = lcrng.outputs(table.start_rng, table.advances[-1] + 200)

    seeds: dict[int, int] = {}
    shifts_seen: dict[int, int] = {}
    for delay in table.walk(0, CALIBRATION_WAITS - 1):
        take_step(emu, game, step_key)
        pid = offspring_personality(game, emu)
        if not pid:
            continue
        high, low = pid >> 16, pid & 0xFFFF
        for seed in range(0x10000):
            if _top16(seed) == high:
                key = (seed - delay) & 0xFFFF
                seeds[key] = seeds.get(key, 0) + 1
        for position in range(max(0, table.advances[delay] - 5), table.advances[delay] + 80):
            if outputs[position] % 0xFFFE + 1 == low:
                shift = position - table.advances[delay]
                shifts_seen[shift] = shifts_seen.get(shift, 0) + 1
    if not seeds or not shifts_seen:
        raise ScriptFailed("No egg was made in the first waits. Are the two Pokémon in the Day Care compatible?")
    frame_offset = max(seeds, key=seeds.get)
    shifts = [shift for shift in sorted(shifts_seen, key=lambda k: -shifts_seen[k]) if shifts_seen[shift] >= 2][:6]
    shifts = shifts or [max(shifts_seen, key=shifts_seen.get)]
    log(f"Calibration: frame counter offset {frame_offset}; the PID's first number comes {shifts} advances after the wait")
    return EggModel(table, frame_offset, shifts)


def shiny_egg_candidates(model: EggModel, trainer_id: int, secret_id: int, max_delay: int, nature: str | None):
    wanted_nature = NATURES.index(nature.title()) if nature else None
    table = model.table
    table.extend_to(max_delay)
    outputs = lcrng.outputs(table.start_rng, table.advances[-1] + 200)
    for delay in range(max_delay):
        high = _top16((delay + model.frame_offset) & 0xFFFF)
        for shift in model.shifts:
            advance = table.advances[delay] + shift
            pid = high << 16 | (outputs[advance] % 0xFFFE + 1)
            if is_shiny(pid, trainer_id, secret_id) and (wanted_nature is None or pid % NATURE_COUNT == wanted_nature):
                yield delay, advance, pid


def find_egg_pid(
    emu: EmulatorInterface, game: Gen3Reader, state: bytes, step_key: int, nature: str | None, max_delay: int, log: Callable[[str], None],
    wanted: set[int] | None = None, wanted_advances=(),
) -> tuple[int, int]:
    trainer_id, secret_id = game.trainer_ids()
    model = calibrate_egg_pid(emu, game, state, step_key, log)
    tried = 0
    for delay, advance, predicted in shiny_egg_candidates(model, trainer_id, secret_id, max_delay, None if wanted else nature):
        if wanted is not None and (predicted not in wanted or (wanted_advances and advance not in wanted_advances)):
            continue
        tried += 1
        model.table.state_after(delay)
        take_step(emu, game, step_key)
        made = offspring_personality(game, emu)
        if wanted is not None:
            found = made in wanted
        else:
            found = bool(made) and is_shiny(made, trainer_id, secret_id) and (nature is None or made % NATURE_COUNT == NATURES.index(nature.title()))
        if found:
            log(f"Shiny egg after waiting {delay:,} frames: PID {made:#010x} (predicted {predicted:#010x}).")
            return delay, made
    if wanted is not None:
        raise ScriptFailed(f"The chosen eggs could not be made within {max_delay:,} frames of waiting ({tried} candidates tried). Choose rows with a ✓ in the Hit column.")
    raise ScriptFailed(f"No shiny egg within {max_delay:,} frames of waiting ({tried} candidates tried).")


def list_shiny_eggs(
    emu: EmulatorInterface, game: Gen3Reader, state: bytes, step_key: int, nature: str | None, max_delay: int, max_advance: int, log: Callable[[str], None]
) -> list[Target]:
    trainer_id, secret_id = game.trainer_ids()
    model = calibrate_egg_pid(emu, game, state, step_key, log)
    rows = []
    for delay, advance, predicted in shiny_egg_candidates(model, trainer_id, secret_id, max_delay, nature):
        if advance > max_advance:
            continue
        model.table.state_after(delay)
        take_step(emu, game, step_key)
        made = offspring_personality(game, emu)
        value = shiny_value(predicted, trainer_id, secret_id)
        rows.append(
            Target(
                advance=advance, pid=predicted, iv_word=0, shiny="Square" if value == 0 else "Star", nature=NATURES[predicted % NATURE_COUNT],
                ability=str((predicted & 1) + 1), ivs=None, hidden_power="—", power=None, gender="—", species="Egg", reachable=made == predicted,
            )
        )
    return sorted(rows, key=lambda row: row.advance)


def take_egg_prompt(emu: EmulatorInterface, game: Gen3Reader) -> None:
    for frame in range(1500):
        if game.game.yes_no_task in game.active_tasks():
            run(emu, 0, 30)
            return
        run(emu, Button.A if frame % 10 == 0 else 0)
    raise ScriptFailed("The Day Care man did not offer the egg. Stand where he can be spoken to (Route 117).")


def egg_after_yes(emu: EmulatorInterface, game: Gen3Reader) -> PartyPokemon | None:
    before = game.party_size()
    for frame in range(240):
        run(emu, Button.A if frame % 2 == 0 else 0)
        if game.party_size() > before:
            return game.newest_party_pokemon()
    return None


def pokefinder_ivs(pokemon: PartyPokemon) -> list[int]:
    ivs = pokemon.ivs
    return [ivs["HP"], ivs["Atk"], ivs["Def"], ivs["SpA"], ivs["SpD"], ivs["Spe"]]


def parent_ivs(game: Gen3Reader, emu: EmulatorInterface) -> list[list[int]]:
    return [pokefinder_ivs(mon) for mon in daycare_mons(game, emu)]


def predict_egg_ivs(outputs: list[int], position: int, parents: list[list[int]]) -> list[int]:
    first, second = outputs[position], outputs[position + 1]
    ivs = [first & 31, (first >> 5) & 31, (first >> 10) & 31, (second >> 5) & 31, (second >> 10) & 31, second & 31]
    inherit = [outputs[position + 3] % 6, outputs[position + 4] % 5, outputs[position + 5] % 4]
    parent = [outputs[position + 6] % 2, outputs[position + 7] % 2, outputs[position + 8] % 2]
    for stats, index, which in (
        (EMERALD_AVAILABLE_1, inherit[0], parent[0]),
        (EMERALD_AVAILABLE_2, inherit[1], parent[1]),
        (EMERALD_AVAILABLE_3, inherit[2], parent[2]),
    ):
        stat = stats[index]
        ivs[stat] = parents[which][stat]
    return ivs


def find_egg_ivs(
    emu: EmulatorInterface, game: Gen3Reader, state: bytes, min_total: int, max_delay: int, log: Callable[[str], None]
) -> tuple[int, PartyPokemon]:
    table = WaitTable(emu, game.rng_address, state)
    table.extend_to(CALIBRATION_WAITS)
    outputs = lcrng.outputs(table.start_rng, table.advances[-1] + 200)
    parents = parent_ivs(game, emu)

    shifts: dict[int, int] = {}
    for delay in table.walk(0, CALIBRATION_WAITS - 1):
        egg = egg_after_yes(emu, game)
        if egg is None:
            continue
        seen = pokefinder_ivs(egg)
        for position in range(max(0, table.advances[delay] - 5), table.advances[delay] + 120):
            if predict_egg_ivs(outputs, position, parents) == seen:
                shift = position - table.advances[delay]
                shifts[shift] = shifts.get(shift, 0) + 1
    if not shifts:
        raise ScriptFailed("Could not find where the egg's IVs are made in the random numbers.")
    shift_list = sorted(shifts, key=lambda k: -shifts[k])[:4]
    log(f"Calibration: the egg's IVs are made {shift_list} advances after the wait")

    table.extend_to(max_delay)
    outputs = lcrng.outputs(table.start_rng, table.advances[-1] + 200)
    best: tuple[int, int] | None = None
    for delay in range(max_delay):
        for shift in shift_list:
            total = sum(predict_egg_ivs(outputs, table.advances[delay] + shift, parents))
            if best is None or total > best[0]:
                best = (total, delay)
        if best[0] >= min_total:
            break
    total, delay = best
    log(f"Best IV total in the range: {total} after waiting {delay:,} frames")
    table.state_after(delay)
    egg = egg_after_yes(emu, game)
    if egg is None:
        raise ScriptFailed("No egg was handed over at the prompt.")
    log(f"  the egg: {' '.join(f'{name} {value}' for name, value in egg.ivs.items())} (total {sum(egg.ivs.values())})")
    return delay, egg


def find_any_egg(emu: EmulatorInterface, game: Gen3Reader, state: bytes, step_key: int) -> tuple[int, int]:
    current = state
    for delay in range(MAX_FIND_EGG_WAIT):
        emu.set_state(current)
        take_step(emu, game, step_key)
        low = offspring_personality(game, emu)
        if low:
            return delay, low
        emu.set_state(current)
        run(emu, 0)
        current = emu.get_state()
    raise ScriptFailed("No egg was made. Are the two Pokémon in the Day Care compatible?")


def predict_rs_egg(outputs: list[int], position: int, variant: tuple[int, int, int], low: int, parents: list[list[int]]) -> tuple[int, list[int]]:
    skip_first, skip_second, skip_inherit = variant
    high = outputs[position]
    at = position + 1 + skip_first
    first = outputs[at]
    at += 1 + skip_second
    second = outputs[at]
    at += 1 + skip_inherit
    inherit = [outputs[at] % 6, outputs[at + 1] % 5, outputs[at + 2] % 4]
    parent = [outputs[at + 3] % 2, outputs[at + 4] % 2, outputs[at + 5] % 2]
    ivs = [first & 31, (first >> 5) & 31, (first >> 10) & 31, (second >> 5) & 31, (second >> 10) & 31, second & 31]
    available = [0, 1, 2, 3, 4, 5]
    for index, size, which in ((inherit[0], 5, parent[0]), (inherit[1], 4, parent[1]), (inherit[2], 3, parent[2])):
        stat = available[index]
        ivs[RS_ORDER[stat]] = parents[which][RS_ORDER[stat]]
        for place in range(stat, size):
            available[place] = available[place + 1]
    return high << 16 | low, ivs


def find_rs_egg(
    emu: EmulatorInterface, game: Gen3Reader, state: bytes, low: int, nature: str | None, max_delay: int, log: Callable[[str], None]
) -> tuple[int, PartyPokemon]:
    trainer_id, secret_id = game.trainer_ids()
    wanted_nature = NATURES.index(nature.title()) if nature else None
    table = WaitTable(emu, game.rng_address, state)
    table.extend_to(CALIBRATION_WAITS)
    outputs = lcrng.outputs(table.start_rng, table.advances[-1] + 300)
    parents = parent_ivs(game, emu)

    found: dict[tuple[tuple[int, int, int], int], int] = {}
    for delay in table.walk(0, CALIBRATION_WAITS - 1):
        egg = egg_after_yes(emu, game)
        if egg is None:
            continue
        seen_ivs = pokefinder_ivs(egg)
        for position in range(max(0, table.advances[delay] - 5), table.advances[delay] + 150):
            for variant in RS_VARIANTS:
                pid, ivs = predict_rs_egg(outputs, position, variant, low, parents)
                if pid == egg.personality_value and ivs == seen_ivs:
                    key = (variant, position - table.advances[delay])
                    found[key] = found.get(key, 0) + 1
    if not found:
        raise ScriptFailed("Could not find where the egg is made in the random numbers.")
    best_count = max(found.values())
    keys = [key for key in sorted(found, key=lambda k: -found[k]) if found[key] * 2 >= best_count][:6]
    log(f"Calibration: (method, advances after the wait) {keys}")

    table.extend_to(max_delay)
    outputs = lcrng.outputs(table.start_rng, table.advances[-1] + 300)
    candidates: list[tuple[int, int]] = []
    for delay in range(max_delay):
        for variant, shift in keys:
            position = table.advances[delay] + shift
            if not is_shiny(outputs[position] << 16 | low, trainer_id, secret_id):
                continue
            pid, ivs = predict_rs_egg(outputs, position, variant, low, parents)
            if wanted_nature is not None and pid % NATURE_COUNT != wanted_nature:
                continue
            candidates.append((sum(ivs), delay))
    if not candidates:
        raise ScriptFailed(f"No shiny egg within {max_delay:,} frames of waiting.")
    candidates.sort(reverse=True)
    for total, delay in candidates[:12]:
        table.state_after(delay)
        egg = egg_after_yes(emu, game)
        if egg is not None and egg.is_shiny:
            log(f"Shiny egg after waiting {delay:,} frames: PID {egg.personality_value:#010x}, IVs {sum(egg.ivs.values())} in all (predicted {total}).")
            return delay, egg
    raise ScriptFailed("The shiny eggs that were predicted did not come.")


class BreedingBot(Bot):

    def __init__(self, game_key: str = "emerald"):
        self.options = OPTIONS if game_key == "emerald" else RUBY_SAPPHIRE_OPTIONS

    def state_problem(self, game):
        return breeding_problem(game)

    @staticmethod
    def _walk_to_the_check(emu, game, log):
        out, back = step_pair(game)
        log(f"Walking back and forth until the Day Care's step count ({day_care_steps(game, emu):#x}) is one step from an egg check ...")
        emu.start_recording()
        key = out
        for _ in range(MAX_WALK_STEPS):
            if day_care_steps(game, emu) & 0xFF == READY_STEP_COUNT:
                break
            before = day_care_steps(game, emu)
            if not take_step(emu, game, key) or day_care_steps(game, emu) == before:
                emu.stop_recording()
                raise ScriptFailed("The Day Care's step count does not go up when walking. Are two Pokémon in the Day Care, and is something in the way?")
            key = back if key == out else out
        else:
            emu.stop_recording()
            raise ScriptFailed("The Day Care's step count did not get to the egg check.")
        return emu.stop_recording(), key

    def list_targets(self, emu, game, start_state, options, max_advance, log):
        emu.set_state(start_state)
        _walk, step_key = self._walk_to_the_check(emu, game, log)
        ready = emu.get_state()
        base = lcrng.distance(game.boot_seed(), emu.read_u32(game.rng_address))
        limit = max(0, max_advance - base)
        rows = list_shiny_eggs(emu, game, ready, step_key, options["nature"], min(limit, MAX_PID_WAIT), limit, log)
        return [replace(row, advance=row.advance + base) for row in rows]

    def hunt(self, emu, game, start_state, options, log):
        emu.set_state(start_state)
        walk, step_key = self._walk_to_the_check(emu, game, log)
        ready = emu.get_state()
        split = game.game.split_egg_pid
        base = 0 if split else lcrng.distance(game.boot_seed(), emu.read_u32(game.rng_address))
        if split:
            wait_pid, low = find_any_egg(emu, game, ready, step_key)
            pid = None
        else:
            wanted = {tuple(key)[0] for key in options["targets"]} if options.get("targets") else None
            max_wait = min(options["target_limit"], MAX_PID_WAIT) if wanted else MAX_PID_WAIT
            advances = [advance - base for advance in options.get("target_advances", ())]
            wait_pid, pid = find_egg_pid(emu, game, ready, step_key, options["nature"], max_wait, log, wanted, advances)
        emu.set_state(ready)
        emu.start_recording()
        run(emu, 0, wait_pid)
        take_step(emu, game, step_key)
        if not split and offspring_personality(game, emu) != pid:
            raise ScriptFailed("The egg was not the predicted one. Nothing was changed.")
        way = find_path(game, (game.game.daycare_man[0], game.game.daycare_man[1] + 1))
        if way is None:
            raise ScriptFailed("There is no way from here to the Day Care man.")
        walk_path(emu, game, way)
        face(emu, Button.UP)
        take_egg_prompt(emu, game)
        second = emu.stop_recording()
        prompt = emu.get_state()
        if split:
            wait_ivs, egg = find_rs_egg(emu, game, prompt, low, options["nature"], MAX_PID_WAIT, log)
            pid = egg.personality_value
        else:
            wait_ivs, egg = find_egg_ivs(emu, game, prompt, MIN_IV_TOTAL, MAX_IV_WAIT, log)
        emu.set_state(prompt)
        emu.start_recording()
        run(emu, 0, wait_ivs)
        egg_after_yes(emu, game)
        third = emu.stop_recording()
        keys = walk + second + third
        play_keys(emu, start_state, keys)
        made = self.result(game)
        if made.personality_value != pid or made.iv_word != egg.iv_word:
            raise ScriptFailed("The recorded buttons did not give the egg that was found. Nothing was changed.")
        return {
            "keys": compress(keys),
            "writes": [],
            "frames": len(keys),
            "delay": wait_pid + wait_ivs,
            "pid": pid,
            "description": made.describe(),
            "attempts": 1,
        }
