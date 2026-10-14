from shiny.hunts.options import BotOptions

OPTIONS = BotOptions(
    name="Fishing",
    supports_targets=True,
    lists_in_worker=True,
    advances_from_boot=False,
    rows_note="IVs are a prediction: the game may use a random number between the PID and the IVs, so they can differ. The rest is exact.",
)
