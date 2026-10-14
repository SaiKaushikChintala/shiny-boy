from dataclasses import dataclass

from shiny.paths import DATA_DIRECTORY

LANGUAGE = "E"
HEADER_CODE_ADDRESS = 0x080000AC
HEADER_REVISION_ADDRESS = 0x080000BC
SUPPORTED_REVISION = 0

SYMBOLS_DIRECTORY = DATA_DIRECTORY / "gen3" / "symbols"


@dataclass(frozen=True)
class Gen3Game:

    key: str
    name: str
    code: str
    symbol_file: str
    fixed_save_blocks: bool
    flags_offset: int
    vars_offset: int
    roamer_offset: int
    daycare_offset: int
    daycare_mon_size: int
    split_egg_pid: bool
    key_items_offset: int
    key_items_count: int
    registered_item_offset: int | None
    start_menu_symbols: tuple[str, str]
    menu_action_save: int
    tile_attribute_offset: int
    tile_attribute_size: int
    primary_metatiles: int
    behaviour_mask: int
    grass_behaviours: frozenset[int] | None
    water_behaviours: frozenset[int] | None
    daycare_map: tuple[int, int]
    daycare_man: tuple[int, int]
    yes_no_task: str
    pending_egg_flag: int
    measured_pre_steps: bool


_RS = dict(
    fixed_save_blocks=True, flags_offset=0x1220, vars_offset=0x1340, roamer_offset=0x3144, daycare_offset=0x2F9C, daycare_mon_size=0x50, split_egg_pid=True,
    key_items_offset=0x5B0, key_items_count=20, registered_item_offset=0x496,
    start_menu_symbols=("sNumStartMenuActions", "sCurrentStartMenuActions"), menu_action_save=5,
    tile_attribute_offset=0x10, tile_attribute_size=2, primary_metatiles=512, behaviour_mask=0xFF, grass_behaviours=None, water_behaviours=None,
    daycare_map=(0, 32), daycare_man=(47, 4), yes_no_task="TASK_HANDLEYESNOINPUT", pending_egg_flag=134, measured_pre_steps=False,
)
RUBY = Gen3Game("ruby", "Ruby", "AXV", "pokeruby.sym", **_RS)
SAPPHIRE = Gen3Game("sapphire", "Sapphire", "AXP", "pokesapphire.sym", **_RS)
EMERALD = Gen3Game(
    "emerald", "Emerald", "BPE", "pokeemerald.sym",
    **{**_RS, "fixed_save_blocks": False, "flags_offset": 0x1270, "vars_offset": 0x139C, "roamer_offset": 0x31DC, "daycare_offset": 0x3030,
       "daycare_mon_size": 0x8C, "split_egg_pid": False, "key_items_offset": 0x5D8, "key_items_count": 30, "registered_item_offset": None},
)
_FRLG = {
    **_RS, "fixed_save_blocks": False, "flags_offset": 0x0EE0, "vars_offset": 0x1000, "roamer_offset": 0x30D0, "daycare_offset": 0x2F80,
    "daycare_mon_size": 0x8C, "key_items_offset": 0x3B8, "key_items_count": 30,
    "registered_item_offset": 0x296, "start_menu_symbols": ("sNumStartMenuItems", "sStartMenuOrder"), "menu_action_save": 4,
    "tile_attribute_offset": 0x14, "tile_attribute_size": 4, "primary_metatiles": 640, "behaviour_mask": 0x1FF,
    "grass_behaviours": frozenset({0x02, 0x08}),
    "water_behaviours": frozenset({0x10, 0x11, 0x12, 0x13, 0x15}),
    "daycare_map": (3, 15), "daycare_man": (16, 13), "yes_no_task": "TASK_YESNOMENU_HANDLEINPUT", "pending_egg_flag": 0x266, "measured_pre_steps": True,
}
FIRERED = Gen3Game("firered", "FireRed", "BPR", "pokefirered.sym", **_FRLG)
LEAFGREEN = Gen3Game("leafgreen", "LeafGreen", "BPG", "pokeleafgreen.sym", **_FRLG)
GAMES = {game.code: game for game in (RUBY, SAPPHIRE, EMERALD, FIRERED, LEAFGREEN)}

PLAYER_NAME_OFFSET = 0x00
PLAYER_GENDER_OFFSET = 0x08
TRAINER_ID_OFFSET = 0x0A

PLAYER_X_OFFSET = 0x00
MAP_GROUP_OFFSET = 0x04
VAR_BASE = 0x4000

TASK_COUNT = 16
TASK_SIZE = 40

OBJECT_EVENT_SIZE = 0x24
OBJECT_EVENT_COUNT = 16
MAP_OFFSET = 7

BLOCK_BLOCKED_MASK = 0x0C00
BLOCK_METATILE_MASK = 0x03FF

ITEM_OLD_ROD = 263
ITEM_GOOD_ROD = 262
ITEM_SUPER_ROD = 264
