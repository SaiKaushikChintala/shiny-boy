import datetime
import tempfile
from multiprocessing.queues import Queue
from pathlib import Path

from shiny.core.emulator.mgba_backend import Emulator
from shiny.core.scan.engine import ScriptFailed
from shiny.games.detect import reader_for_emulator
from shiny.hunts.registry import bots_for


def make_emulator(rom_path: str, save_data: bytes | None, clock: datetime.datetime | None) -> Emulator:
    if save_data:
        save = Path(tempfile.gettempdir()) / "shiny_boy_worker.sav"
        save.write_bytes(save_data)
        emulator = Emulator(rom_path, save)
    else:
        emulator = Emulator(rom_path)
    if clock is not None:
        emulator.set_fixed_clock(clock)
    emulator.set_video_enabled(False)
    return emulator


def _use_boot_seed(game, options: dict) -> None:
    if options.get("boot_seed") is not None and hasattr(game, "boot_seed_value"):
        game.boot_seed_value = options["boot_seed"]


def run_list(
    rom_path: str,
    start_state: bytes,
    bot_name: str,
    options: dict,
    max_advance: int,
    queue: Queue,
    clock: datetime.datetime | None = None,
    save_data: bytes | None = None,
) -> None:
    try:
        emulator = make_emulator(rom_path, save_data, clock)
        game = reader_for_emulator(emulator)
        _use_boot_seed(game, options)
        rows = bots_for(game)[bot_name].list_targets(emulator, game, start_state, options, max_advance, lambda text: queue.put(("log", text)))
    except ScriptFailed as error:
        queue.put(("fail", str(error)))
        return
    except Exception as error:
        queue.put(("fail", f"{type(error).__name__}: {error}"))
        return
    queue.put(("table", rows))


def run_hunt(
    rom_path: str,
    start_state: bytes,
    bot_name: str,
    options: dict,
    queue: Queue,
    clock: datetime.datetime | None = None,
    save_data: bytes | None = None,
) -> None:
    try:
        emulator = make_emulator(rom_path, save_data, clock)
        game = reader_for_emulator(emulator)
        _use_boot_seed(game, options)
        plan = bots_for(game)[bot_name].hunt(emulator, game, start_state, options, lambda text: queue.put(("log", text)))
    except ScriptFailed as error:
        queue.put(("fail", str(error)))
        return
    except Exception as error:
        queue.put(("fail", f"{type(error).__name__}: {error}"))
        return
    queue.put(("done", plan))
