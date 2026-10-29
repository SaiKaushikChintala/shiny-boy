import functools
import multiprocessing
import tempfile
from pathlib import Path
from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.emulator.mgba_backend import Emulator
from shiny.core.pokemon.gb_model import GbPokemon
from shiny.core.scan.delay_search import DEFAULT_BLOCK, find_first_hit
from shiny.core.scan.engine import Attempt, HuntResult, ScriptFailed
from shiny.games.detect import reader_for_emulator
from shiny.hunts.base import Bot

MAX_DELAY = 2_000_000
BACKGROUND_PROCESSES = 1


def rebuild(hunt_class: type["TimerHunt"], rom_path, clock, start_state: bytes, options: dict, save_data: bytes | None = None) -> "TimerHunt":
    if save_data:
        name = multiprocessing.current_process().name.replace(" ", "_")
        save = Path(tempfile.gettempdir()) / f"shiny_boy_{name}.sav"
        save.write_bytes(save_data)
        emulator = Emulator(rom_path, save)
    else:
        emulator = Emulator(rom_path)
    if clock is not None:
        emulator.set_fixed_clock(clock)
    emulator.set_video_enabled(False)
    return hunt_class(emulator, reader_for_emulator(emulator), start_state, options, lambda text: None)


class TimerHunt:

    A_FRAMES_ON = 3
    A_PERIOD = 20
    LEAD_FRAMES = 60
    GIVE_TIMEOUT = 600
    BASELINE_TIMEOUT = 2400
    BLOCK = DEFAULT_BLOCK
    NO_POKEMON_MESSAGE = "No Pokémon was made. Start from a state shortly before it."
    species: int | None = None

    def __init__(self, emu: EmulatorInterface, game, start_state: bytes, options: dict, log: Callable[[str], None] = print):
        self.emu, self.game, self.options, self.log = emu, game, options, log
        self.start_state = start_state
        self.prelude_keys: list[int] = []
        self.snapshot = self._take_snapshot()

    def prepare(self) -> None:
        pass

    def _given(self) -> bool:
        return self.game.party_size() != 0

    def outcome(self) -> GbPokemon | None:
        for frame in range(self.GIVE_TIMEOUT):
            self._run(self._a_key(frame), 1)
            if self._given():
                self._run(0, 10)
                return self.game.newest_party_pokemon()
        return None

    def _run(self, key: int, frames: int) -> None:
        self.emu.set_keys(key)
        for _ in range(frames):
            self.emu.run_frame()

    def _a_key(self, frame: int) -> int:
        return Button.A if frame % self.A_PERIOD < self.A_FRAMES_ON else 0

    def _take_snapshot(self) -> bytes:
        emu = self.emu
        emu.set_state(self.start_state)
        emu.start_recording()
        self._run(0, 1)
        self.prepare()
        prelude = emu.stop_recording()
        before = emu.get_state()
        given_after = None
        for frame in range(self.BASELINE_TIMEOUT):
            self._run(self._a_key(frame), 1)
            if self._given():
                given_after = frame
                break
        if given_after is None or given_after < self.LEAD_FRAMES:
            raise ScriptFailed(self.NO_POKEMON_MESSAGE)
        emu.set_state(before)
        emu.start_recording()
        for frame in range(given_after - self.LEAD_FRAMES):
            self._run(self._a_key(frame), 1)
        self.prelude_keys = prelude + emu.stop_recording()
        return emu.get_state()

    def state_after(self, delay: int) -> None:
        self.emu.set_state(self.snapshot)
        self._run(0, delay)

    def _run_script(self) -> GbPokemon:
        pokemon = self.outcome()
        if pokemon is None:
            raise ScriptFailed(self.NO_POKEMON_MESSAGE)
        return pokemon

    def _is_wanted(self, pokemon: GbPokemon) -> bool:
        return pokemon.is_shiny and (self.species is None or pokemon.species == self.species)

    def scan(self, first_delay: int, last_delay: int) -> list[tuple[int, GbPokemon]]:
        cached = getattr(self, "_scan_cache", None)
        if cached is not None and cached[0] <= first_delay:
            self.emu.set_state(cached[1])
            self._run(0, first_delay - cached[0])
        else:
            self.emu.set_state(self.snapshot)
            self._run(0, first_delay)
        hits = []
        for delay in range(first_delay, last_delay):
            here = self.emu.get_state()
            pokemon = self.outcome()
            if pokemon is not None and self._is_wanted(pokemon):
                hits.append((delay, pokemon))
            self.emu.set_state(here)
            self._run(0, 1)
        self._scan_cache = (last_delay, self.emu.get_state())
        return hits

    def run(self, max_delay: int) -> HuntResult | None:
        builder = functools.partial(rebuild, type(self), self.emu.rom_path, self.emu.fixed_clock, self.start_state, self.worker_options(), self.emu.save_data)
        workers = max(1, (multiprocessing.cpu_count() or 2) - BACKGROUND_PROCESSES)
        hit = find_first_hit(builder, max_delay, workers, self.log, self.BLOCK)
        if hit is None:
            return None
        delay = hit[0]
        self.state_after(delay)
        pokemon = self._run_script()
        if not self._is_wanted(pokemon):
            raise ScriptFailed("The Pokémon that was found did not come again when the wait was repeated. Nothing was changed.")
        self.log(f"Found: a wait of {delay:,} frames makes {pokemon.describe()}")
        return HuntResult(Attempt(delay, pokemon, 0), delay + 1)

    def worker_options(self) -> dict:
        return self.options

    def unreachable_message(self) -> None:
        return None


class TimerBot(Bot):

    def limit(self, options: dict) -> int:
        return MAX_DELAY

    def result(self, game, plan: dict | None = None) -> GbPokemon:
        return game.enemy_pokemon() if game.in_battle() else game.newest_party_pokemon()

    def _hunt_timer(self, emu, game, start_state: bytes, hunt: TimerHunt, options: dict) -> dict:
        found = hunt.run(self.limit(options))
        if found is None:
            raise ScriptFailed(self.not_found(hunt, options))
        return self._plan(emu, game, start_state, hunt, found, hunt.prelude_keys, getattr(hunt, "prelude_writes", ()))
