from shiny.hunts.options import BotOptions

EMERALD_OPTIONS = BotOptions(
    name="Roamer",
    choices=("Latias", "Latios"),
    choice_label="Answer (red / blue)",
    supports_targets=True,
    target_level="40",
)

OPTIONS = BotOptions(name="Roamer", supports_targets=True, target_level="40-50")
