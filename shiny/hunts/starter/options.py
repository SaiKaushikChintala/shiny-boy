from shiny.hunts.options import BotOptions

STARTER_NAMES = ("Treecko", "Torchic", "Mudkip")

OPTIONS = BotOptions(
    name="Starter",
    choices=STARTER_NAMES,
    choice_label="Starter",
    supports_targets=True,
    target_level="5",
)

FRLG_OPTIONS = BotOptions(
    name="Starter",
    choices=("Bulbasaur", "Squirtle", "Charmander"),
    choice_label="Starter",
    supports_targets=True,
    target_level="5",
)
