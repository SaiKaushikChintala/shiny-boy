from shiny.core.emulator.buttons import Button
from shiny.core.scan.engine import ScriptFailed
from shiny.games.gen2.layout import load_targets
from shiny.hunts.gen2.starter.hunt import Gen2StarterHunt
from shiny.hunts.gen2.static.options import STARTERS, options_for
from shiny.hunts.scene_hunt import SceneHunt
from shiny.hunts.timer_hunt import TimerBot


class Gen2TargetHunt(SceneHunt):

    STABLE_FRAMES = 40
    SUBTRACT_STABLE = True
    ADJUST_TIMEOUT = True

    @staticmethod
    def load_targets(game: str) -> dict[str, dict]:
        return load_targets(game)

    def menu_ready(self) -> bool:
        return self.game.byte("wMenuDataItems") == 4 and self.game.byte("wMenuCursorY") == 1

    def gift_made(self) -> bool:
        return self.game.party_size() > self.party_before

    def after_menu_comes(self, places: int):
        yield from self._wait(20)
        for _ in range(places):
            yield from self._press(Button.DOWN)
            yield from self._wait(10)
        yield from self._press(Button.A)
        yield from self._wait(10)


class Gen2TargetBot(TimerBot):

    def __init__(self, game_key: str, kind: str):
        self.options = options_for(game_key, kind)

    def state_problem(self, game):
        return "Be in the overworld first (not in a battle)." if game.in_battle() else None

    def goal(self, options):
        return f"a shiny {options['choice']}"

    def hunt(self, emu, game, start_state, options, log):
        if options["choice"] in STARTERS:
            if game.party_size() != 0:
                raise ScriptFailed("You already have a Pokémon. Load a state in front of the starter first.")
            starter = Gen2StarterHunt(emu, game, start_state, {**options, "choice": options["choice"].lower()}, log)
            return self._hunt_timer(emu, game, start_state, starter, options)
        return self._hunt_timer(emu, game, start_state, Gen2TargetHunt(emu, game, start_state, options, log), options)
