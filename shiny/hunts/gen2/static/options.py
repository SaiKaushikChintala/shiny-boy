from shiny.games.gen2.layout import load_targets
from shiny.hunts.options import BotOptions

STARTERS = ("Chikorita", "Cyndaquil", "Totodile")


def options_for(game_key: str, kind: str) -> BotOptions:
    labels = [spec["label"] for spec in load_targets(game_key).values() if (spec["kind"] == "static") == (kind == "static")]
    return BotOptions(
        name=kind.title(),
        choices=tuple(sorted(labels + ([] if kind == "static" else list(STARTERS)), key=str.lower)),
        choice_label="Pokémon",
        choices_as_buttons=False,
        has_nature=False,
        saves_first=True,
        rows_note="Gen 2 has no table: its random numbers come from a hardware timer, so nothing can be listed beforehand.",
    )
