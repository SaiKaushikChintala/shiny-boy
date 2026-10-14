import bisect
from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PARTY_POKEMON_SIZE, PartyPokemon, parse_party_pokemon
from shiny.core.pokemon.natures import NATURE_COUNT, NATURES
from shiny.core.rng import lcrng
from shiny.core.rng.method1 import method1_iv_word
from shiny.core.rng.method_h import shiny_wild_starts, wild_pid
from shiny.core.scan.engine import HUNT_SNAPSHOT_EVERY, Attempt, HuntResult, ScriptFailed
from shiny.core.scan.wait_table import WaitTable
from shiny.games.gen3.inputs import run
from shiny.games.gen3.reader import Gen3Reader

MAX_PRESS_FRAMES = 200
COMPLETE_WITHIN_FRAMES = 60

IV_PATTERNS = ((0, 1), (1, 2), (0, 2))


class EncounterTry:

    def __init__(self, emu: EmulatorInterface, game: Gen3Reader):
        self.emulator, self.game = emu, game
        self._previous_pid = 0

    def start_watching(self) -> None:
        self._previous_pid = self.game.enemy_pid()

    def _enemy_exists(self) -> bool:
        return self.game.enemy_pid() not in (0, self._previous_pid)

    def _finished_enemy(self) -> PartyPokemon | None:
        for _ in range(COMPLETE_WITHIN_FRAMES):
            data = self.game.read_symbol("gEnemyParty", 0, PARTY_POKEMON_SIZE)
            pokemon = parse_party_pokemon(data)
            if int.from_bytes(data[88:90], "little") != 0 and pokemon.checksum_is_valid and pokemon.species != 0:
                return pokemon
            run(self.emulator, 0)
        return None

    def play(self, key: int = Button.A, pulse: bool = True, max_frames: int = MAX_PRESS_FRAMES) -> PartyPokemon | None:
        self.start_watching()
        for frame in range(max_frames):
            run(self.emulator, key if (not pulse or frame % 2 == 0) else 0)
            if self._enemy_exists():
                return self._finished_enemy()
        return None


class WildHunt:
    OFFSETS: tuple[int, ...] = ()
    OFFSET_WINDOW = (1, 12)
    CALIBRATION_WAITS = range(100, 130)
    TRY_CLASS = EncounterTry

    def __init__(
        self,
        emu: EmulatorInterface,
        game: Gen3Reader,
        start_state: bytes,
        nature: str | None = None,
        log: Callable[[str], None] = print,
        snapshot_every: int = HUNT_SNAPSHOT_EVERY,
    ):
        self.emu, self.game, self.log = emu, game, log
        self.start_state = start_state
        self.nature = nature.title() if nature else None
        self.finder = self._make_finder()
        self.table = WaitTable(emu, game.rng_address, start_state, progress=self._progress, snapshot_every=snapshot_every)
        ids = game.trainer_ids()
        if ids is None:
            raise ScriptFailed("The game has no player yet (no save data in memory). Start from a state in the game.")
        self.trainer_id, self.secret_id = ids
        self.start_rng = self.table.start_rng
        self.attempts_made = 0
        self.offsets = tuple(self.OFFSETS)
        self.target_pids: set[int] | None = None
        self.target_starts: set[int] = set()
        self.unreachable: list[int] = []
        self.advance_base = 0
        self.iv_pattern: tuple[int, int] | None = None

    def _make_finder(self) -> EncounterTry:
        return self.TRY_CLASS(self.emu, self.game)

    def _progress(self, delay: int, advances: int, speed: float) -> None:
        if delay % 32768 == 0:
            self.log(f"Wait table: {delay:,} frames ({speed:,.0f} frames/s)")

    def state_after(self, delay: int) -> bytes:
        return self.table.state_after(delay)

    def aim(self, keys: set[tuple[int, int]], advances=(), base: int = 0) -> None:
        self.target_pids = {pid for pid, _iv_word in keys}
        self.target_starts = {advance - base for advance in advances}
        self.advance_base = base

    def unreachable_message(self) -> str | None:
        if not self.unreachable:
            return None
        where = ", ".join(f"{start + self.advance_base:,}" for start in sorted(self.unreachable))
        return (f"The chosen Pokémon (advance {where}) can't be hit exactly: waiting skips some RNG advances, and this one is one of "
                "them. Choose a row with a ✓ in the Hit column.")

    def _wanted(self, pokemon: PartyPokemon) -> bool:
        if self.target_pids is not None:
            return pokemon.personality_value in self.target_pids
        return pokemon.is_shiny and (self.nature is None or pokemon.nature == self.nature)

    def calibrate(self) -> None:
        self.table.extend_to(max(self.CALIBRATION_WAITS) + 1)
        low, high = self.OFFSET_WINDOW
        numbers = lcrng.outputs(self.start_rng, max(self.table.advances) + high + 8)
        seen: dict[int, int] = {}
        patterns: dict[tuple[int, int], int] = {}
        for delay in self.table.walk(self.CALIBRATION_WAITS.start, self.CALIBRATION_WAITS.stop - 1):
            waited = self.table.advances[delay]
            pokemon = self.finder.play()
            if pokemon is None:
                continue
            starts = [
                start - waited
                for start in range(waited + low, waited + high + 1)
                if (wild_pid(numbers, start) or (0, -1, 0))[1] == pokemon.personality_value
            ]
            if len(starts) == 1:
                seen[starts[0]] = seen.get(starts[0], 0) + 1
                end = wild_pid(numbers, waited + starts[0])[2]
                for pattern in IV_PATTERNS:
                    if end + max(pattern) < len(numbers) and method1_iv_word(numbers[end + pattern[0]], numbers[end + pattern[1]]) == pokemon.iv_word:
                        patterns[pattern] = patterns.get(pattern, 0) + 1
        if patterns:
            self.iv_pattern = max(patterns, key=lambda pattern: patterns[pattern])
        if seen:
            self.offsets = tuple(sorted(seen, key=lambda offset: -seen[offset]))
            self.log("Calibration: the Pokémon starts " + ", ".join(f"{offset} advances after the wait ({seen[offset]}x)" for offset in self.offsets))
        else:
            self.log(f"Calibration found no clear start; trying {self.offsets}")

    def _run_script(self) -> PartyPokemon:
        pokemon = self.finder.play()
        if pokemon is None:
            raise ScriptFailed("No Pokémon appeared.")
        return pokemon

    def _delay_for_start(self, start: int, offset: int, max_delay: int) -> int | None:
        wanted_advances = start - offset
        if wanted_advances < 0:
            return None
        while self.table.advances[-1] < wanted_advances:
            if self.table.last_delay >= max_delay:
                return None
            self.table.extend_to(min(self.table.last_delay + self.table.snapshot_every, max_delay))
        position = bisect.bisect_left(self.table.advances, wanted_advances)
        if position > self.table.last_delay or self.table.advances[position] != wanted_advances:
            return None
        return position

    def _learn_offsets(self, offsets: list[int], delay: int, pokemon: PartyPokemon, numbers: list[int]) -> None:
        waited = self.table.advances[delay]
        low, high = self.OFFSET_WINDOW
        for candidate in range(waited + low, waited + high + 1):
            found = wild_pid(numbers, candidate)
            if found is not None and found[1] == pokemon.personality_value and candidate - waited not in offsets and len(offsets) < 8:
                offsets.append(candidate - waited)

    def hits(self, start: int, pid: int, max_delay: int, numbers: list[int]) -> bool:
        offsets = list(self.offsets)
        for offset in offsets:
            delay = self._delay_for_start(start, offset, max_delay)
            if delay is None:
                continue
            self.table.state_after(delay)
            pokemon = self.finder.play()
            if pokemon is None:
                continue
            if pokemon.personality_value == pid:
                return True
            self._learn_offsets(offsets, delay, pokemon, numbers)
        return False

    def run(self, max_delay: int = 40000) -> HuntResult | None:
        self.calibrate()
        count = int(max_delay * 1.3) + 600
        numbers = lcrng.outputs(self.start_rng, count)
        for start, pid in shiny_wild_starts(numbers, self.trainer_id, self.secret_id, 0, count - 400):
            predicted_nature = NATURES[pid % NATURE_COUNT]
            if self.target_pids is not None and (pid not in self.target_pids or (self.target_starts and start not in self.target_starts)):
                continue
            if self.target_pids is None and self.nature is not None and predicted_nature != self.nature:
                continue
            self.log(f"Shiny candidate: the Pokémon would start to be made at position {start:,} (PID {pid:#010x}, {predicted_nature})")
            offsets = list(self.offsets)
            for offset in offsets:
                delay = self._delay_for_start(start, offset, max_delay)
                if delay is None:
                    continue
                self.attempts_made += 1
                self.table.state_after(delay)
                pokemon = self.finder.play()
                if pokemon is None:
                    continue
                if pokemon.personality_value == pid:
                    if not self._wanted(pokemon):
                        self.log(f"  wait {delay:,}: {pokemon.describe()} (not wanted)")
                        break
                    self.log(f"  wait {delay:,}: {pokemon.describe()}")
                    return HuntResult(Attempt(delay, pokemon, start), self.attempts_made)
                self.log(f"  wait {delay:,}: made {pokemon.personality_value:#010x}, not the predicted one")
                self._learn_offsets(offsets, delay, pokemon, numbers)
            if self.target_pids is not None:
                self.unreachable.append(start)
        return None
