from shiny.core.emulator.buttons import Button
from shiny.core.pokemon.gb_model import GbPokemon
from shiny.core.scan.engine import ScriptFailed
from shiny.games.gen1.layout import dex_event, load_targets
from shiny.hunts.gen1.static.options import options_for
from shiny.hunts.scene_hunt import SceneHunt
from shiny.hunts.timer_hunt import TimerBot

PRIZE_MENU = (3, 4, 1)
MENU_SETTLE_FRAMES = 90


class Gen1TargetHunt(SceneHunt):

    STATIC_SETTLE_FRAMES = 1

    @staticmethod
    def load_targets(game: str) -> dict[str, dict]:
        return load_targets(game)

    def menu_ready(self) -> bool:
        last_entry, row, column = PRIZE_MENU
        return self.game.byte("wMaxMenuItem") == last_entry and self.game.byte("wTopMenuItemY") == row and self.game.byte("wTopMenuItemX") == column

    def gift_made(self) -> bool:
        last = self.game.party_size() - 1
        return last >= self.party_before and self.game.party_pokemon_made(last)

    def _a_key(self, frame: int) -> int:
        if not self.static and self.game.party_size() > self.party_before:
            return Button.B if frame % self.A_PERIOD < self.A_FRAMES_ON else 0
        return super()._a_key(frame)

    def after_menu_comes(self, places: int):
        yield from self._wait(MENU_SETTLE_FRAMES)
        yield from self._move_cursor(self.game.byte("wCurrentMenuItem"), places)
        yield from self._press(Button.A)
        yield from self._wait(10)

    def extra_scene(self, intro: str):
        return self._flute_scene() if intro == "flute" else None

    def _flute_scene(self):
        game = self.game
        yield from self._press(Button.START)
        yield from self._wait(30)
        event = dex_event(game.key)
        has_pokedex = (game.byte("wEventFlags", event // 8) >> (event % 8)) & 1
        yield from self._move_cursor(game.byte("wCurrentMenuItem"), 2 if has_pokedex else 1)
        yield from self._press(Button.A)
        yield from self._wait(30)
        flute = self.spec["item"]
        bag = [game.byte("wBagItems", 2 * index) for index in range(game.byte("wNumBagItems"))]
        if flute not in bag:
            raise ScriptFailed("There is no Poké Flute in the bag.")
        here = game.byte("wCurrentMenuItem") + game.byte("wListScrollOffset")
        yield from self._move_cursor(here, bag.index(flute))
        yield from self._press(Button.A)
        yield from self._wait(20)

    def made_gift(self) -> GbPokemon:
        self._run(0, 10)
        return self.game.newest_party_pokemon()


class Gen1TargetBot(TimerBot):

    def __init__(self, game_key: str):
        self.options = options_for(game_key)

    def state_problem(self, game):
        return "Be in the overworld first (not in a battle)." if game.in_battle() else None

    def goal(self, options):
        return f"a {options['choice']} with shiny DVs"

    def hunt(self, emu, game, start_state, options, log):
        return self._hunt_timer(emu, game, start_state, Gen1TargetHunt(emu, game, start_state, options, log), options)
