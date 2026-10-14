from shiny.games.gen1.layout import load_targets
from shiny.hunts.options import BotOptions


def options_for(game_key: str) -> BotOptions:
    return BotOptions(
        name="Gift or static",
        choices=tuple(spec["label"] for spec in load_targets(game_key).values()),
        choice_label="Pokémon",
        choices_as_buttons=False,
        has_nature=False,
        saves_first=True,
        rows_note="Gen 1 has no table: its random numbers come from a hardware timer, so nothing can be listed beforehand.",
    )
