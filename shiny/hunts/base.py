from dataclasses import replace
from typing import Callable

from shiny.core.emulator.interface import EmulatorError, EmulatorInterface
from shiny.core.pokemon.model import PartyPokemon
from shiny.core.rng import lcrng
from shiny.core.scan.engine import HuntResult, ScriptFailed
from shiny.games.gen3.reader import Gen3Reader
from shiny.hunts.options import BotOptions
from shiny.hunts.plan import compress, play_keys
from shiny.hunts.targets import mark_reachable, wild_targets

MAX_DELAY = 40000
MAX_DELAY_WITH_NATURE = 1_500_000
REACH_LIMIT = 40_000
NOT_OVERWORLD = "Be in the overworld first (not in a menu, a battle or a cutscene)."


class Bot:
    options: BotOptions

    def problem(self, game: Gen3Reader | None, options: dict | None = None) -> str | None:
        if game is None:
            return "This bot needs Pokémon Ruby, Sapphire, Emerald, FireRed or LeafGreen (the English version)."
        try:
            return self.state_problem(game)
        except EmulatorError as error:
            return f"The game is not ready: {error}"

    def state_problem(self, game: Gen3Reader) -> str | None:
        return None

    def target_level(self, options: dict) -> str:
        return self.options.target_level

    def goal(self, options: dict) -> str:
        return "a shiny Pokémon"

    def target_species(self, game: Gen3Reader, options: dict) -> str | None:
        return None

    def list_targets(self, emu: EmulatorInterface, game: Gen3Reader, start_state: bytes, options: dict, max_advance: int, log: Callable[[str], None]) -> list:
        raise NotImplementedError

    def hunt(self, emu: EmulatorInterface, game: Gen3Reader, start_state: bytes, options: dict, log: Callable[[str], None]) -> dict:
        raise NotImplementedError

    def result(self, game: Gen3Reader, plan: dict | None = None) -> PartyPokemon:
        return game.newest_party_pokemon()

    @staticmethod
    def max_delay(nature: str | None) -> int:
        return MAX_DELAY_WITH_NATURE if nature else MAX_DELAY

    def limit(self, options: dict) -> int:
        if options.get("targets"):
            return options["target_limit"]
        return self.max_delay(options["nature"])

    def start_advance(self, hunt) -> int:
        seed = hunt.game.boot_seed() if self.options.advances_from_boot else None
        return 0 if seed is None else lcrng.distance(seed, hunt.start_rng)

    def aim(self, hunt, options: dict) -> None:
        if options.get("targets"):
            hunt.aim({tuple(key) for key in options["targets"]}, options.get("target_advances", ()), self.start_advance(hunt))

    def not_found(self, hunt, options: dict) -> str:
        if options.get("targets"):
            return hunt.unreachable_message() or "The chosen Pokémon could not be reached within the wait limit."
        return f"No shiny found within {self.limit(options):,} frames of waiting."

    def _plan(
        self, emu: EmulatorInterface, game: Gen3Reader, start_state: bytes, hunt, found: HuntResult, prelude: list[int],
        prelude_writes=(), extra: dict | None = None,
    ) -> dict:
        delay = found.attempt.delay
        hunt.state_after(delay)
        emu.start_recording()
        hunt._run_script()
        script_keys = emu.stop_recording()
        keys = prelude + [0] * delay + script_keys

        writes = [[frame, kind, address, data.hex()] for frame, kind, address, data in prelude_writes]
        play_keys(emu, start_state, keys, writes)
        made = self.result(game, extra)
        if made.personality_value != found.attempt.pokemon.personality_value:
            raise ScriptFailed("The recorded buttons did not give the Pokémon that was found. Nothing was changed.")
        return {
            "keys": compress(keys),
            "writes": writes,
            "frames": len(keys),
            "delay": delay,
            "pid": made.personality_value,
            "description": made.describe(),
            "attempts": found.attempts_made,
            **(extra or {}),
        }

    def _hunt_and_plan(self, emu: EmulatorInterface, game: Gen3Reader, start_state: bytes, hunt, options: dict, prelude=(), prelude_writes=()) -> dict:
        self.aim(hunt, options)
        found = hunt.run(self.limit(options))
        if found is None:
            raise ScriptFailed(self.not_found(hunt, options))
        return self._plan(emu, game, start_state, hunt, found, list(prelude), prelude_writes)


class WildBot(Bot):

    def result(self, game: Gen3Reader, plan: dict | None = None) -> PartyPokemon:
        return game.enemy_pokemon(0)

    def state_problem(self, game: Gen3Reader) -> str | None:
        if not game.in_overworld():
            return NOT_OVERWORLD
        return None

    def _wild_rows(self, hunt, slots: list[tuple[int, int, int]], kind: str, options: dict, max_advance: int) -> list:
        hunt.calibrate()
        rows = wild_targets(
            hunt.start_rng, hunt.trainer_id, hunt.secret_id, max_advance, slots, kind, options["nature"], hunt.iv_pattern or (0, 1)
        )
        rows = mark_reachable(rows, hunt, REACH_LIMIT)
        base = self.start_advance(hunt)
        return [replace(row, advance=row.advance + base) for row in rows] if base else rows
