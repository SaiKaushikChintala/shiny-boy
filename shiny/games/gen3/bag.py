from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.scan.engine import ScriptFailed
from shiny.games.gen3.inputs import MENU_ACTION_BAG, cursor_to_action, run, tap
from shiny.games.gen3.reader import Gen3Reader

KEY_ITEMS_POCKET = 4
BAG_POSITION_POCKET = 5
BAG_POSITION_CURSORS = 8


def move_to_key_item(emu: EmulatorInterface, game: Gen3Reader, item: int, name: str) -> None:
    items = game.key_items()
    if item not in items:
        raise ScriptFailed(f"There is no {name} in the bag (it is a Key Item).")
    index = items.index(item)
    position = game.symbol("gBagPosition")[0]
    for _ in range(8):
        if emu.read_bytes(position + BAG_POSITION_POCKET)[0] == KEY_ITEMS_POCKET:
            break
        tap(emu, Button.RIGHT, 16)
    else:
        raise ScriptFailed("Could not get to the Key Items pocket of the bag.")
    for _ in range(60):
        cursor = int.from_bytes(emu.read_bytes(position + BAG_POSITION_CURSORS + KEY_ITEMS_POCKET * 2, 2), "little")
        scroll = int.from_bytes(emu.read_bytes(position + BAG_POSITION_CURSORS + 10 + KEY_ITEMS_POCKET * 2, 2), "little")
        if cursor + scroll == index:
            return
        tap(emu, Button.DOWN if cursor + scroll < index else Button.UP, 10)
    raise ScriptFailed(f"Could not move the bag's cursor to the {name}.")


def open_key_item_menu(emu: EmulatorInterface, game: Gen3Reader, item: int, name: str) -> bytes:
    if item not in game.key_items():
        raise ScriptFailed(f"There is no {name} in the bag (it is a Key Item).")
    run(emu, 0, 20)
    tap(emu, Button.START, 30)
    cursor_to_action(emu, game, MENU_ACTION_BAG)
    tap(emu, Button.A, 90)
    if game.callback_name() != "CB2_BAGMENURUN":
        raise ScriptFailed("Could not open the bag. Close any menu or message first.")
    move_to_key_item(emu, game, item, name)
    tap(emu, Button.A, 25)
    if "TASK_ITEMCONTEXT_MULTIPLEROWS" not in game.active_tasks():
        raise ScriptFailed(f"Could not open the item menu of the {name}.")
    return emu.get_state()
