from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.scan.engine import HUNT_SNAPSHOT_EVERY, ScriptFailed
from shiny.games.gen3.reader import Gen3Reader
from shiny.games.gen3.walking import face, find_path, walk_path
from shiny.hunts.base import NOT_OVERWORLD, Bot
from shiny.hunts.gift.hunt import GiftHunt
from shiny.hunts.starter.options import FRLG_OPTIONS

OAKS_LAB = (4, 3)
BALL_ROW = 4
BALL_COLUMNS = {"bulbasaur": 8, "squirtle": 9, "charmander": 10}
SPECIES = {"bulbasaur": "Bulbasaur", "squirtle": "Squirtle", "charmander": "Charmander"}


class BallHunt(GiftHunt):

    NO_POKEMON_MESSAGE = "No Pokémon was given. Stand in Oak's lab with no Pokémon in the party, and try again."

    def __init__(self, emu: EmulatorInterface, game: Gen3Reader, start_state: bytes, starter: str, nature, log, snapshot_every: int = HUNT_SNAPSHOT_EVERY):
        self.starter = starter
        super().__init__(emu, game, start_state, nature, log, snapshot_every)

    def _run_script(self) -> PartyPokemon:
        pokemon = super()._run_script()
        if pokemon.species_name != SPECIES[self.starter]:
            raise ScriptFailed(f"Got {pokemon.species_name} instead of {SPECIES[self.starter]}.")
        return pokemon


class FrlgStarterBot(Bot):

    options = FRLG_OPTIONS

    def goal(self, options):
        return f"a shiny {options['choice'].title()}"

    def target_species(self, game, options):
        return options["choice"]

    def state_problem(self, game):
        if not game.in_overworld():
            return NOT_OVERWORLD
        if game.party_size() != 0:
            return "You already have a Pokémon. Load a state in Oak's lab, before the starter is chosen."
        if game.map_group_and_number() != OAKS_LAB:
            return "Stand in Oak's lab in Pallet Town first (the starters are on the table)."
        return None

    def _walk_to_the_ball(self, emu, game, starter: str) -> list[int]:
        stand = (BALL_COLUMNS[starter], BALL_ROW + 1)
        way = find_path(game, stand)
        if way is None:
            raise ScriptFailed("There is no way to the table in Oak's lab. Stand where you can walk to it (nobody in the way).")
        emu.start_recording()
        walk_path(emu, game, way)
        face(emu, Button.UP)
        return emu.stop_recording()

    def hunt(self, emu, game, start_state, options, log):
        emu.set_state(start_state)
        walk = self._walk_to_the_ball(emu, game, options["choice"])
        hunt = BallHunt(emu, game, emu.get_state(), options["choice"], options["nature"], log)
        return self._hunt_and_plan(emu, game, start_state, hunt, options, walk)
