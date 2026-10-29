from shiny.hunts.base import Bot
from shiny.hunts.fossil.hunt import FossilBot
from shiny.hunts.gift.hunt import GiftBot
from shiny.hunts.options import BotOptions
from shiny.hunts.starter.frlg import FrlgStarterBot
from shiny.hunts.starter.hunt import StarterBot
from shiny.hunts.starter.options import FRLG_OPTIONS, OPTIONS as RSE_STARTER_OPTIONS

FOSSIL = "Fossil"
FRLG = ("firered", "leafgreen")


class Gen3GiftBot(Bot):

    def __init__(self, game_key: str):
        frlg = game_key in FRLG
        self.starter = FrlgStarterBot() if frlg else StarterBot()
        self.fossil = None if frlg else FossilBot()
        self.other = GiftBot()
        starters = (FRLG_OPTIONS if frlg else RSE_STARTER_OPTIONS).choices
        choices = list(starters) + ([] if self.fossil is None else [FOSSIL])
        self.starter_names = {name.lower() for name in starters}
        self.options = BotOptions(
            name="Gift",
            choices=tuple(sorted(choices, key=str.lower)),
            choice_label="Pokémon",
            choices_as_buttons=False,
            supports_targets=True,
        )

    def _pick(self, options: dict | None) -> tuple[Bot, dict | None]:
        choice = (options or {}).get("choice") or ""
        if choice.lower() in self.starter_names:
            return self.starter, {**options, "choice": choice.lower()}
        if choice == FOSSIL and self.fossil is not None:
            return self.fossil, options
        return self.other, options

    def problem(self, game, options: dict | None = None):
        bot, options = self._pick(options)
        return bot.problem(game, options)

    def target_level(self, options: dict) -> str:
        bot, options = self._pick(options)
        return bot.target_level(options)

    def goal(self, options: dict) -> str:
        bot, options = self._pick(options)
        return bot.goal(options)

    def target_species(self, game, options: dict):
        bot, options = self._pick(options)
        return bot.target_species(game, options)

    def hunt(self, emu, game, start_state, options, log):
        bot, options = self._pick(options)
        return bot.hunt(emu, game, start_state, options, log)
