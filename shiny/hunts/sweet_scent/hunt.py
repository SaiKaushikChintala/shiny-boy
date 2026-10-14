from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.scan.engine import ScriptFailed
from shiny.games.gen3.encounters import slots_for
from shiny.games.gen3.inputs import MENU_ACTION_POKEMON, cursor_to_action, run, tap
from shiny.games.gen3.reader import Gen3Reader
from shiny.hunts.base import WildBot
from shiny.hunts.sweet_scent.options import OPTIONS
from shiny.hunts.wild.hunt import EncounterTry, WildHunt

SWEET_SCENT_START_OFFSET = 263
MAX_FRAMES = 600


PARTY_TASKS = {
    "ruby": ("HANDLEDEFAULTPARTYMENU", "SUB_8089D94"),
    "sapphire": ("HANDLEDEFAULTPARTYMENU", "SUB_8089D94"),
    "emerald": ("TASK_HANDLECHOOSEMONINPUT", "TASK_HANDLESELECTIONMENUINPUT"),
    "firered": ("TASK_HANDLECHOOSEMONINPUT", "TASK_HANDLESELECTIONMENUINPUT"),
    "leafgreen": ("TASK_HANDLECHOOSEMONINPUT", "TASK_HANDLESELECTIONMENUINPUT"),
}


def open_sweet_scent_menu(emu: EmulatorInterface, game: Gen3Reader) -> bytes:
    if not game.in_overworld():
        raise ScriptFailed("Be in the overworld, standing in tall grass.")
    choose_task, selection_task = PARTY_TASKS[game.key]
    run(emu, 0, 20)
    tap(emu, Button.START, 30)
    cursor_to_action(emu, game, MENU_ACTION_POKEMON)
    tap(emu, Button.A, 90)
    if choose_task not in game.active_tasks():
        raise ScriptFailed("Could not open the party menu. Close any menu or message first and use the Pokémon item once.")
    tap(emu, Button.A, 40)
    if selection_task not in game.active_tasks():
        raise ScriptFailed("Could not open the menu of the first Pokémon.")
    if not game.game.fixed_save_blocks:
        tap(emu, Button.DOWN, 20)
    return emu.get_state()


class SweetScentTry(EncounterTry):

    def play(self) -> PartyPokemon | None:
        self.start_watching()
        run(self.emulator, Button.A, 2)
        for _ in range(MAX_FRAMES):
            run(self.emulator, 0)
            if self._enemy_exists():
                return self._finished_enemy()
        return None


class SweetScentHunt(WildHunt):

    OFFSETS = (SWEET_SCENT_START_OFFSET,)
    OFFSET_WINDOW = (240, 290)
    TRY_CLASS = SweetScentTry


class SweetScentBot(WildBot):

    options = OPTIONS

    def list_targets(self, emu, game, start_state, options, max_advance, log):
        emu.set_state(start_state)
        menu = open_sweet_scent_menu(emu, game)
        slots = slots_for(game, "land")
        if slots is None:
            raise ScriptFailed("There are no grass encounters on this map.")
        hunt = SweetScentHunt(emu, game, menu, options["nature"], log)
        return self._wild_rows(hunt, slots, "land", options, max_advance)

    def hunt(self, emu, game, start_state, options, log):
        emu.set_state(start_state)
        emu.start_recording()
        menu = open_sweet_scent_menu(emu, game)
        menu_keys = emu.stop_recording()
        emu.set_state(menu)
        if SweetScentTry(emu, game).play() is None:
            raise ScriptFailed("Sweet Scent did not start an encounter. Stand in tall grass, with a first Pokémon that knows it.")
        hunt = SweetScentHunt(emu, game, menu, options["nature"], log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options, menu_keys)
