from shiny.core.emulator.buttons import Button
from shiny.core.pokemon.model import PartyPokemon
from shiny.games.gen3.encounters import slots_for
from shiny.hunts.base import WildBot
from shiny.hunts.rock_smash.options import OPTIONS
from shiny.hunts.wild.hunt import EncounterTry, WildHunt

SMASH_FRAMES = 700
ROCK_SMASH_MAX_DELAY = 1_500_000


class RockSmashTry(EncounterTry):

    def play(self, key: int = Button.A, pulse: bool = True, max_frames: int = SMASH_FRAMES) -> PartyPokemon | None:
        return super().play(Button.A, True, SMASH_FRAMES)


class RockSmashHunt(WildHunt):

    OFFSETS = (160, 190, 220)
    OFFSET_WINDOW = (20, 3000)
    CALIBRATION_WAITS = range(100, 260)
    TRY_CLASS = RockSmashTry


class RockSmashBot(WildBot):

    options = OPTIONS

    def limit(self, options):
        return super().limit(options) if options.get("targets") else ROCK_SMASH_MAX_DELAY

    def list_targets(self, emu, game, start_state, options, max_advance, log):
        emu.set_state(start_state)
        slots = slots_for(game, "rock")
        if slots is None:
            from shiny.core.scan.engine import ScriptFailed

            raise ScriptFailed("There are no Rock Smash encounters on this map.")
        hunt = RockSmashHunt(emu, game, start_state, options["nature"], log)
        return self._wild_rows(hunt, slots, "rock", options, max_advance)

    def hunt(self, emu, game, start_state, options, log):
        hunt = RockSmashHunt(emu, game, start_state, options["nature"], log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options)
