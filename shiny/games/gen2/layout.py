import json
from functools import cache

from shiny.games.gameboy import PartyLayout
from shiny.paths import DATA_DIRECTORY

TITLES = {"POKEMON_GLD": "gold", "POKEMON_SLV": "silver", "PM_CRYSTAL": "crystal"}

PARTY = PartyLayout(structure="wPartyMon1DVs", dv_offset=0, size=48, made_symbol="wPartySpecies", made_step=1)
BATTLE_SYMBOL = "wBattleMode"
TILEMAP_SYMBOL = "wTilemap"


@cache
def load_targets(game: str) -> dict[str, dict]:
    raw = json.loads((DATA_DIRECTORY / "gen2" / "targets.json").read_text(encoding="utf-8"))
    return raw[game]["targets"]
