from shiny.hunts.options import BotOptions

NO_TABLE = "Gen 1 has no table: its random numbers come from a hardware timer, so nothing can be listed beforehand."
STARTER_NAMES = ("Bulbasaur", "Charmander", "Squirtle")

OPTIONS = BotOptions(name="Starter", choices=STARTER_NAMES, choice_label="Starter", has_nature=False, saves_first=True, rows_note=NO_TABLE)
OPTIONS_YELLOW = BotOptions(name="Pikachu", has_nature=False, saves_first=True, rows_note=NO_TABLE)
