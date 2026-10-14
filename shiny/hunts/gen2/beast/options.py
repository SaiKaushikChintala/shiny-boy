from shiny.hunts.options import BotOptions

BEASTS_OF = {"gold": ("Raikou", "Entei", "Suicune"), "silver": ("Raikou", "Entei", "Suicune"), "crystal": ("Raikou", "Entei")}


def options_for(game_key: str) -> BotOptions:
    return BotOptions(
        name="Roaming beast",
        choices=BEASTS_OF[game_key],
        choice_label="Beast",
        has_nature=False,
        saves_first=True,
        rows_note="Gen 2 has no table: its random numbers come from a hardware timer, so nothing can be listed beforehand.",
    )
