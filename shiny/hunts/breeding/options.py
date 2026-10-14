from dataclasses import replace

from shiny.hunts.options import BotOptions

OPTIONS = BotOptions(
    name="Breeding",
    supports_targets=True,
    lists_in_worker=True,
    rows_note=(
        "These are the shiny eggs that waiting up to 60,000 frames can make. Their IVs are made later, when the egg is taken: the bot then "
        "waits for the best it can find."
    ),
)

RUBY_SAPPHIRE_OPTIONS = replace(OPTIONS, supports_targets=False, lists_in_worker=False, rows_note="", saves_first=True)
