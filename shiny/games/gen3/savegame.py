import datetime

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.rng import lcrng
from shiny.core.scan.engine import ScriptFailed
from shiny.games.gen3.inputs import cursor_to_action
from shiny.games.gen3.reader import Gen3Reader

RELOAD_CLOCK = datetime.datetime(2000, 1, 1, 12, 0, 0)
SAVE_WRITE_FRAMES = 420
SAVE_MAX_FRAMES = 1800
BOOT_MAX_FRAMES = 4000
BOOT_PRESS_EVERY = 30
SEEDED_CALLBACK = "CB2_INITCOPYRIGHTSCREENAFTERBOOTUP"
SEED_JUMP = 1000
BOOT_SETTLE_FRAMES = 120

SECTOR_SIZE = 0x1000
SAVE_SECTORS = 28
SECTOR_SIGNATURE_OFFSET = 0xFF8
SECTOR_SIGNATURE = 0x08012025


def _hold(emu: EmulatorInterface, key: int, frames: int) -> None:
    emu.set_keys(key)
    emu.run_frames(frames)


def highest_counter(save_data: bytes) -> int:
    best = 0
    for sector in range(SAVE_SECTORS):
        footer = sector * SECTOR_SIZE + SECTOR_SIGNATURE_OFFSET
        if footer + 8 > len(save_data):
            break
        if int.from_bytes(save_data[footer : footer + 4], "little") == SECTOR_SIGNATURE:
            best = max(best, int.from_bytes(save_data[footer + 4 : footer + 8], "little"))
    return best


def align_save_counter(emu: EmulatorInterface, game: Gen3Reader, save_data: bytes) -> None:
    wanted = highest_counter(save_data)
    address = game.symbol("gSaveCounter")[0]
    if int.from_bytes(emu.read_bytes(address, 4), "little") < wanted:
        emu.write_bytes(address, wanted.to_bytes(4, "little"))


def save_in_game(emu: EmulatorInterface, game: Gen3Reader) -> None:
    if not game.in_overworld():
        raise ScriptFailed("Be in the overworld to save (not in a menu, a battle or a cutscene).")
    _hold(emu, 0, 20)
    _hold(emu, Button.START, 2)
    _hold(emu, 0, 30)
    cursor_to_action(emu, game, game.game.menu_action_save)
    before = int.from_bytes(game.read_symbol("gSaveCounter"), "little")
    _hold(emu, Button.A, 2)
    _hold(emu, 0, 120)
    for _ in range(SAVE_MAX_FRAMES // 40):
        if int.from_bytes(game.read_symbol("gSaveCounter"), "little") != before:
            break
        _hold(emu, Button.A, 2)
        _hold(emu, 0, 38)
    else:
        raise ScriptFailed("The game did not save. Close any menu or message and try again.")
    _hold(emu, 0, SAVE_WRITE_FRAMES)
    for _ in range(3):
        _hold(emu, Button.B, 2)
        _hold(emu, 0, 40)
    _hold(emu, 0, 20)


def reload_from_save(emu: EmulatorInterface, game: Gen3Reader) -> None:
    emu.reset()
    emu.set_keys(0)
    frame = 0
    seeded = game.key == "emerald"
    previous = None
    while not game.in_overworld():
        if frame >= BOOT_MAX_FRAMES:
            raise ScriptFailed("The game did not get to the overworld after a reset. Is there a save to continue from?")
        emu.set_keys(Button.A if frame % BOOT_PRESS_EVERY < 3 else 0)
        emu.run_frame()
        frame += 1
        if not seeded:
            value = game.rng_value()
            if game.game.fixed_save_blocks:
                if game.callback_name() == SEEDED_CALLBACK:
                    game.boot_seed_value, seeded = value, True
            elif previous is not None and lcrng.distance(previous, value) > SEED_JUMP:
                game.boot_seed_value, seeded = value, True
            previous = value
    _hold(emu, 0, BOOT_SETTLE_FRAMES)
