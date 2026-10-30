from shiny.core.emulator.buttons import Button
from shiny.core.pokemon.gb_model import GbPokemon
from shiny.core.scan.engine import ScriptFailed
from shiny.games.gen1.layout import dex_event, load_targets
from shiny.hunts.gen1.starter.hunt import EMPTY_PARTY, Gen1StarterHunt, YellowPikachuHunt
from shiny.hunts.gen1.static.options import options_for
from shiny.hunts.scene_hunt import SceneHunt
from shiny.hunts.timer_hunt import TimerBot

PRIZE_MENU = (3, 4, 1)
MENU_SETTLE_FRAMES = 90

CINNABAR_LAB_FOSSIL_ROOM = 170
FOSSIL_GAVE_EVENT = 736
FOSSIL_REVIVING_EVENT = 737
FOSSIL_TALK_FRAMES = 3000
FOSSIL_CLOSE_FRAMES = 300
FOSSIL_LEAD = 20


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
        return last >= self.party_before and self.game.party_pokemon_made(last) and self.game.byte("wPartyMons", last * 44) == self.game.byte("wPartySpecies", last)

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
        if intro == "flute":
            return self._flute_scene()
        return self._fossil_scene() if intro == "fossil" else None

    def choose_lead(self, start: bytes, scripted_until: int, made_at: int, given_after: int) -> int:
        if self.lead is None and self.spec["intro"] == "fossil":
            self.lead = FOSSIL_LEAD
        return super().choose_lead(start, scripted_until, made_at, given_after)

    def _event_set(self, event: int) -> bool:
        return bool((self.game.byte("wEventFlags", event // 8) >> (event % 8)) & 1)

    def _fossil_scene(self):
        if self.game.byte("wCurMap") != CINNABAR_LAB_FOSSIL_ROOM:
            raise ScriptFailed("Stand in front of the scientist in the Cinnabar Lab's fossil room, facing him, with a fossil in the bag.")
        if self.game.party_size() >= 6:
            raise ScriptFailed("The party is full, so the revived Pokémon would go to the PC. Deposit one Pokémon first.")
        for frame in range(FOSSIL_TALK_FRAMES):
            if self._event_set(FOSSIL_GAVE_EVENT):
                break
            yield Button.A if frame % self.A_PERIOD < self.A_FRAMES_ON else 0
        else:
            raise ScriptFailed("The scientist did not take a fossil. Put one in the bag and stand right in front of him, facing him.")
        for frame in range(FOSSIL_CLOSE_FRAMES):
            yield Button.B if frame % self.A_PERIOD < self.A_FRAMES_ON else 0
        byte, bit = FOSSIL_REVIVING_EVENT // 8, FOSSIL_REVIVING_EVENT % 8
        self._write("wEventFlags", bytes([self.game.byte("wEventFlags", byte) & ~(1 << bit) & 0xFF]), byte)
        yield 0

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

    def __init__(self, game_key: str, kind: str):
        self.options = options_for(game_key, kind)

    def state_problem(self, game):
        return "Be in the overworld first (not in a battle)." if game.in_battle() else None

    def goal(self, options):
        return f"a {options['choice']} with shiny DVs"

    def hunt(self, emu, game, start_state, options, log):
        spec = Gen1TargetHunt.find_target(game.key, options["choice"])
        if spec["intro"] == "starter":
            emu.set_state(start_state)
            if game.party_size() != 0:
                raise ScriptFailed(EMPTY_PARTY)
            if game.key == "yellow":
                hunt = YellowPikachuHunt(emu, game, start_state, {**options, "choice": None}, log)
            else:
                hunt = Gen1StarterHunt(emu, game, start_state, {**options, "choice": spec["label"].split()[0].lower()}, log)
            return self._hunt_timer(emu, game, start_state, hunt, options)
        return self._hunt_timer(emu, game, start_state, Gen1TargetHunt(emu, game, start_state, options, log), options)
