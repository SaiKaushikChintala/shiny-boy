import json
from functools import cache

from shiny.games.gameboy import PartyLayout
from shiny.paths import DATA_DIRECTORY

TITLES = {"POKEMON RED": "red", "POKEMON BLU": "blue", "POKEMON YEL": "yellow"}

PARTY = PartyLayout(structure="wPartyMons", dv_offset=27, size=44, made_symbol="wPartyMons", made_step=44)
BATTLE_SYMBOL = "wIsInBattle"
TILEMAP_SYMBOL = "wTileMap"


@cache
def load_targets(game: str) -> dict[str, dict]:
    raw = json.loads((DATA_DIRECTORY / "gen1" / "targets.json").read_text(encoding="utf-8"))
    return raw[game]["targets"]


def dex_event(game: str) -> int:
    return json.loads((DATA_DIRECTORY / "gen1" / "targets.json").read_text(encoding="utf-8"))[game]["dex_event"]
