from shiny.hunts.options import BotOptions

STARTER_NAMES = ("Cyndaquil", "Totodile", "Chikorita")

OPTIONS = BotOptions(
    name="Starter",
    choices=STARTER_NAMES,
    choice_label="Starter",
    has_nature=False,
    saves_first=True,
    rows_note="Gen 2 has no table: its random numbers come from a hardware timer, so nothing can be listed beforehand.",
)
