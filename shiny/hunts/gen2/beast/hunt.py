from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.gb_model import GbPokemon
from shiny.core.scan.engine import ScriptFailed
from shiny.hunts.gen2.beast.options import options_for
from shiny.hunts.timer_hunt import TimerBot, TimerHunt

BEASTS = {"raikou": 243, "entei": 244, "suicune": 245}
BATTLETYPE_ROAMING = 5
COLL_TALL_GRASS = 0x18
TILE_SYMBOLS = {Button.UP: "wTileUp", Button.DOWN: "wTileDown", Button.LEFT: "wTileLeft", Button.RIGHT: "wTileRight"}
STEP_FRAMES = 26
SETTLE_FRAMES = 250
FIRST_READ = 175
INTRO_FRAMES = 400


def grass_step(game) -> int | None:
    for key, symbol in TILE_SYMBOLS.items():
        if game.byte(symbol) == COLL_TALL_GRASS:
            return key
    return None


class BeastHunt(TimerHunt):

    BLOCK = 1000
    NO_POKEMON_MESSAGE = "No beast met. Stand next to tall grass on the route where the beast roams."

    def __init__(self, emu: EmulatorInterface, game, start_state: bytes, options: dict, log: Callable[[str], None] = print):
        self.species = BEASTS[options["choice"].lower()]
        emu.set_state(start_state)
        self.step_key = grass_step(game)
        if self.step_key is None:
            raise ScriptFailed("There is no tall grass next to the player. Stand beside tall grass on the route where the beast roams.")
        super().__init__(emu, game, start_state, options, log)

    def _take_snapshot(self) -> bytes:
        self.emu.set_state(self.start_state)
        self.emu.start_recording()
        self._run(0, 1)
        self.prelude_keys = self.emu.stop_recording()
        return self.emu.get_state()

    def outcome(self) -> GbPokemon | None:
        game = self.game
        for _ in range(STEP_FRAMES):
            self._run(self.step_key, 1)
            if game.byte("wBattleType") == BATTLETYPE_ROAMING and game.byte("wTempWildMonSpecies") == self.species:
                break
        else:
            return None
        for frame in range(SETTLE_FRAMES + INTRO_FRAMES):
            self._run(self._a_key(frame), 1)
            if frame >= FIRST_READ and game.enemy_species() == self.species and game.in_battle():
                self._read_at = frame
                return game.enemy_pokemon()
        return None

    def _run_script(self) -> GbPokemon:
        pokemon = super()._run_script()
        for frame in range(self._read_at + 1, SETTLE_FRAMES + 40):
            self._run(self._a_key(frame), 1)
            if frame >= SETTLE_FRAMES and self.game.enemy_species() == self.species and self.game.in_battle():
                if self.game.enemy_pokemon().dv_bytes != pokemon.dv_bytes:
                    raise ScriptFailed("The DVs of the beast were not the same at the end of the battle's introduction.")
                return pokemon
        raise ScriptFailed("The battle of the beast did not settle.")

    def scan(self, first_delay: int, last_delay: int) -> list[tuple[int, GbPokemon]]:
        cached = getattr(self, "_scan_cache", None)
        if cached is not None and cached[0] <= first_delay + 1:
            self.emu.set_state(cached[1])
            self._run(0, first_delay + 1 - cached[0])
        else:
            self.emu.set_state(self.snapshot)
            self._run(0, first_delay + 1)
        hits = []
        at = first_delay + 1
        for delay in range(first_delay + 1, last_delay, 2):
            here = self.emu.get_state()
            pokemon = self.outcome()
            if pokemon is not None and self._is_wanted(pokemon):
                hits.append((delay, pokemon))
            self.emu.set_state(here)
            self._run(0, 2)
            at = delay + 2
        self._scan_cache = (at, self.emu.get_state())
        return hits


class BeastBot(TimerBot):

    def __init__(self, game_key: str):
        self.options = options_for(game_key)

    def state_problem(self, game):
        if game.in_battle():
            return "Be in the overworld first (not in a battle)."
        if grass_step(game) is None:
            return "Stand next to tall grass, on the route where the beast roams now."
        return None

    def goal(self, options):
        return f"a shiny {options['choice']}"

    def hunt(self, emu, game, start_state, options, log):
        return self._hunt_timer(emu, game, start_state, BeastHunt(emu, game, start_state, options, log), options)
