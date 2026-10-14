from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorError, EmulatorInterface
from shiny.games.gen3.reader import Gen3Reader

MENU_ACTION_POKEMON = 1
MENU_ACTION_BAG = 2


def run(emu: EmulatorInterface, key: int, frames: int = 1) -> None:
    emu.set_keys(key)
    for _ in range(frames):
        emu.run_frame()


def tap(emu: EmulatorInterface, key: int, wait: int) -> None:
    run(emu, key, 2)
    run(emu, 0, wait)


def cursor_to_action(emu: EmulatorInterface, game: Gen3Reader, action: int) -> None:
    try:
        count_symbol, actions_symbol = game.game.start_menu_symbols
        count = emu.read_bytes(game.symbol(count_symbol)[0])[0]
        actions = list(emu.read_bytes(game.symbol(actions_symbol)[0], count))
        cursor = emu.read_bytes(game.symbol("sStartMenuCursorPos")[0])[0]
    except EmulatorError:
        return
    if action not in actions:
        return
    for _ in range(abs(actions.index(action) - cursor)):
        tap(emu, Button.DOWN if actions.index(action) > cursor else Button.UP, 12)
