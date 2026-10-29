import bisect
import statistics
from dataclasses import dataclass
from typing import Callable, Protocol

from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.pokemon.natures import NATURES
from shiny.core.rng.method1 import locate_generation, method1_at, shiny_positions
from shiny.core.scan.wait_table import WaitTable

CALIBRATION_DELAYS = (100, 130, 170, 220, 280)

HUNT_SNAPSHOT_EVERY = 2048


class ScriptFailed(Exception):
    pass


class HuntGame(Protocol):

    rng_address: int

    def trainer_ids(self) -> tuple[int, int] | None: ...


@dataclass
class Attempt:
    delay: int
    pokemon: PartyPokemon
    rng_position: int


@dataclass
class HuntResult:
    attempt: Attempt
    attempts_made: int


class Method1Hunt:
    NO_POKEMON_MESSAGE = "No Pokémon appeared."

    def __init__(
        self,
        emu: EmulatorInterface,
        game: HuntGame,
        start_state: bytes,
        nature: str | None = None,
        log: Callable[[str], None] = print,
        snapshot_every: int = HUNT_SNAPSHOT_EVERY,
    ):
        if nature is not None and nature.title() not in NATURES:
            raise ValueError(f"Unknown nature: {nature}")
        self.emu = emu
        self.game = game
        self.start_state = start_state
        self.nature = nature.title() if nature else None
        self.log = log

        self.table = WaitTable(emu, game.rng_address, start_state, progress=self._table_progress, snapshot_every=snapshot_every)
        ids = game.trainer_ids()
        if ids is None:
            raise ScriptFailed("The game has no player yet (no save data in memory). Start from a state in the game.")
        self.trainer_id, self.secret_id = ids
        self.start_rng = self.table.start_rng
        self.attempts_made = 0
        self.offset: int | None = None
        self.measured: list[int] = []
        self.target_keys: set[tuple[int, int]] | None = None
        self.unreachable: list[int] = []

    def _run_script(self) -> PartyPokemon:
        raise NotImplementedError

    def _table_progress(self, delay: int, advances: int, speed: float) -> None:
        if delay % 32768 == 0:
            self.log(f"Wait table: {delay:,} frames, {advances:,} advances ({speed:,.0f} frames/s)")

    def attempt(self, delay: int) -> Attempt | None:
        self.table.state_after(delay)
        self.attempts_made += 1
        try:
            pokemon = self._run_script()
        except ScriptFailed as error:
            self.log(f"  delay {delay}: {error}")
            return None

        position = None
        waited = self.table.advances[delay]
        if self.offset is not None:
            expected = self.offset + waited
            position = locate_generation(self.start_rng, pokemon, expected - 300, expected + 300)
        if position is None:
            position = locate_generation(self.start_rng, pokemon, 0, waited + 1500)
        if position is None:
            self.log(f"  delay {delay}: could not find where the {pokemon.species_name} came from in the RNG")
            return None
        return Attempt(delay, pokemon, position)

    def state_after(self, delay: int) -> bytes:
        return self.table.state_after(delay)

    def aim(self, keys: set[tuple[int, int]], advances=(), base: int = 0) -> None:
        self.target_keys = keys

    def unreachable_message(self) -> str | None:
        if not self.unreachable:
            return None
        names = ", ".join(f"{method1_at(self.start_rng, position)[0]:08X}" for position in self.unreachable)
        return f"The chosen Pokémon ({names}) can't be hit exactly: waiting skips some RNG advances, and this one is one of them. Choose other rows."

    def is_wanted(self, pokemon: PartyPokemon) -> bool:
        if self.target_keys is not None:
            return (pokemon.personality_value, pokemon.iv_word) in self.target_keys
        return pokemon.is_shiny and (self.nature is None or pokemon.nature == self.nature)

    def _is_target(self, position: int) -> bool:
        return method1_at(self.start_rng, position) in self.target_keys

    def calibrate(self) -> None:
        self.table.extend_to(max(CALIBRATION_DELAYS))
        measured = []
        for delay in CALIBRATION_DELAYS:
            result = self.attempt(delay)
            if result is not None:
                measured.append(result.rng_position - self.table.advances[delay])
        if not measured:
            raise ScriptFailed(self.NO_POKEMON_MESSAGE)
        self.measured = measured
        self.offset = int(statistics.median(measured))
        self.log(f"Calibration: generation happens {measured} advances after the wait -> using {self.offset}")

    def _wait_table_covers(self, advances: int, max_delay: int) -> bool:
        while self.table.advances[-1] < advances:
            if self.table.last_delay >= max_delay:
                return False
            self.table.extend_to(min(self.table.last_delay + self.table.snapshot_every, max_delay))
        return True

    def run(self, max_delay: int = 40000) -> HuntResult | None:
        self.calibrate()

        scan_limit = int(max_delay * 1.3) + self.offset + 2000
        for position in shiny_positions(self.start_rng, scan_limit, self.trainer_id, self.secret_id, self.nature):
            if self.target_keys is not None and not self._is_target(position):
                continue
            if not self._wait_table_covers(position - self.offset + 64, max_delay):
                return None
            found = self._hit_position(position)
            if found is not None:
                return found
            if self.target_keys is not None:
                self.unreachable.append(position)
        return None

    def _hit_position(self, position: int) -> HuntResult | None:
        self.log(f"Shiny candidate at RNG position {position:,}")
        tried: set[int] = set()
        for _ in range(8):
            wanted_advances = position - self.offset
            delay = bisect.bisect_left(self.table.advances, wanted_advances)
            if delay > self.table.last_delay:
                return None

            for candidate in (delay, delay + 1, delay - 1, delay + 2):
                if 1 <= candidate <= self.table.last_delay and candidate not in tried:
                    delay = candidate
                    break
            else:
                return None
            tried.add(delay)

            result = self.attempt(delay)
            if result is None:
                continue
            expected = self.offset + self.table.advances[delay]
            self.log(
                f"  delay {delay:,}: RNG position {result.rng_position:,} (expected {expected:,}) "
                f"-> {result.pokemon.describe()}"
            )
            if self.is_wanted(result.pokemon):
                return HuntResult(result, self.attempts_made)
            self.offset = result.rng_position - self.table.advances[delay]
        return None
