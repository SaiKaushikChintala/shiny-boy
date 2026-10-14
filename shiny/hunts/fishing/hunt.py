from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.scan.engine import ScriptFailed
from shiny.games.gen3 import layout
from shiny.games.gen3.bag import open_key_item_menu
from shiny.games.gen3.encounters import RODS as ROD_KINDS
from shiny.games.gen3.encounters import slots_for
from shiny.games.gen3.inputs import run, tap
from shiny.games.gen3.reader import Gen3Reader
from shiny.hunts.base import WildBot
from shiny.hunts.fishing.options import OPTIONS
from shiny.hunts.wild.hunt import WildHunt

RODS = ("Old Rod", "Good Rod", "Super Rod")

STEP_WAIT_FOR_A = 7
STEP_NEXT_ROUND = 8
STEP_ON_THE_HOOK = 10
STEP_ENDED = (11, 12, 13, 14, 15)
ROD_DATA_INDEX = 15

MAX_FRAMES = 4000
MAX_CASTS = 400
MESSAGE_FRAMES = 120

ROD_ITEMS = (layout.ITEM_SUPER_ROD, layout.ITEM_GOOD_ROD, layout.ITEM_OLD_ROD)


def open_rod_menu(emu: EmulatorInterface, game: Gen3Reader) -> tuple[bytes, int]:
    if not game.in_overworld():
        raise ScriptFailed("Be in the overworld, standing at the water's edge and facing the water.")
    if game.game.registered_item_offset is not None:
        registered = int.from_bytes(emu.read_bytes(game.save_block_1_address() + game.game.registered_item_offset, 2), "little")
        if registered not in ROD_ITEMS:
            raise ScriptFailed("Put your fishing rod on the Select button first (Bag, Key Items, the rod, Register), then stand at the water's edge facing the water.")
        run(emu, 0, 20)
        return emu.get_state(), Button.SELECT
    items = game.key_items()
    rod = next((item for item in ROD_ITEMS if item in items), None)
    if rod is None:
        raise ScriptFailed("There is no fishing rod in the bag (it is a Key Item).")
    return open_key_item_menu(emu, game, rod, "fishing rod"), Button.A


def cast_until_hooked(
    emu: EmulatorInterface, game: Gen3Reader, rod_menu_state: bytes, use_key: int, log: Callable[[str], None] = print
) -> tuple[bytes, str, list[int]]:
    for wait in range(MAX_CASTS):
        emu.set_state(rod_menu_state)
        emu.start_recording()
        rod = _cast(emu, game, wait, use_key)
        cast_keys = emu.stop_recording()
        if rod is not None:
            log(f"A Pokémon is on the hook ({rod}, after waiting {wait} frames before the cast).")
            return emu.get_state(), rod, cast_keys
    raise ScriptFailed("No bite came. Stand at the water's edge, facing the water, where the rod can be used.")


def _cast(emu: EmulatorInterface, game: Gen3Reader, wait: int, use_key: int) -> str | None:
    run(emu, 0, wait)
    tap(emu, use_key, 0)
    bite_answered = False
    message_shown_for = 0
    rod = None
    for _ in range(MAX_FRAMES):
        data = game.task_data("TASK_FISHING", ROD_DATA_INDEX + 1)
        if data is None:
            if rod is None:
                run(emu, 0)
                continue
            return None
        rod = RODS[data[ROD_DATA_INDEX]] if data[ROD_DATA_INDEX] < len(RODS) else "a rod"
        step = data[0]
        key = 0
        if step == STEP_WAIT_FOR_A and not bite_answered:
            key, bite_answered = Button.A, True
        elif step == STEP_NEXT_ROUND:
            bite_answered = False
        if step in STEP_ENDED:
            return None
        if step == STEP_ON_THE_HOOK:
            message_shown_for += 1
            if message_shown_for > MESSAGE_FRAMES:
                return rod
        run(emu, key)
    return None


class FishingHunt(WildHunt):

    OFFSETS = (7, 4)


class FishingBot(WildBot):

    options = OPTIONS

    def list_targets(self, emu, game, start_state, options, max_advance, log):
        emu.set_state(start_state)
        menu, use_key = open_rod_menu(emu, game)
        hooked, rod, _keys = cast_until_hooked(emu, game, menu, use_key, log)
        slots = slots_for(game, "fishing")
        if slots is None:
            raise ScriptFailed("There are no fishing encounters on this map.")
        hunt = FishingHunt(emu, game, hooked, options["nature"], log)
        return self._wild_rows(hunt, slots, ROD_KINDS[rod], options, max_advance)

    def hunt(self, emu, game, start_state, options, log):
        emu.set_state(start_state)
        emu.start_recording()
        menu, use_key = open_rod_menu(emu, game)
        menu_keys = emu.stop_recording()
        hooked, rod, cast_keys = cast_until_hooked(emu, game, menu, use_key, log)
        log(f"Fishing with the {rod}.")
        hunt = FishingHunt(emu, game, hooked, options["nature"], log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options, menu_keys + cast_keys)
