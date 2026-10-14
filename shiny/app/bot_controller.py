import datetime
import multiprocessing
import queue
import subprocess
from typing import TYPE_CHECKING

from shiny.app.ui.theme import STATUS_COLORS, P
from shiny.app.workers import run_hunt, run_list
from shiny.core.emulator.interface import EmulatorError
from shiny.core.pokemon.model import PartyPokemon
from shiny.games.gen3.savegame import RELOAD_CLOCK
from shiny.hunts import targets
from shiny.hunts.plan import apply_writes, expand, writes_by_frame
from shiny.hunts.registry import bots_for

if TYPE_CHECKING:
    from shiny.app.window import Viewer

POLL_MS = 100
MIN_TARGET_LIMIT = 1000
TARGET_LIMIT_MARGIN = 500


def stop_process_tree(process) -> None:
    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class BotController:
    def __init__(self, app: "Viewer"):
        self.app = app
        self.state: str | None = None
        self.process = None
        self.queue = None
        self.bot = None
        self.plan: dict = {}
        self.replay = None
        self.replay_writes: dict = {}
        self.replay_frames = 0

    @property
    def panel(self):
        return self.app.bot_panel

    def is_active(self) -> bool:
        if self.state is not None:
            self.app.set_status("A bot is running. Press Stop in the Bots panel first.", "warning")
            return True
        return False

    def refuse(self, message: str) -> None:
        self.panel.set_status(message, P.warning)
        self.app.set_status(message, "warning")

    def save_bytes(self) -> bytes | None:
        try:
            return self.app.save_path.read_bytes()
        except OSError:
            return None


    def generate_targets(self) -> None:
        app = self.app
        name = self.panel.selected_bot()
        if name is None or app.game is None or self.is_active():
            return
        bot = bots_for(app.game)[name]
        if not bot.options.supports_targets:
            self.panel.set_status("This bot has no table yet.", P.warning)
            return
        problem = bot.problem(app.game)
        if problem is not None:
            self.refuse(problem)
            return
        options = self.panel.chosen_options()
        if bot.options.advances_from_boot:
            self.panel.set_status("Saving, then loading the game from its start ...", P.accent)
            app.window.update_idletasks()
            if not app.files.save_game() or not app.files.reload_game():
                return
        app.update_info()
        if not app.loop.user_paused:
            app.loop.toggle_pause()
        if bot.options.lists_in_worker:
            self.start_listing(bot, options)
            return
        try:
            species = bot.target_species(app.game, options)
            trainer_id, secret_id = app.game.trainer_ids()
            start_rng = app.game.rng_value()
            base = app.game.advances()
            rows = targets.method1_targets(
                start_rng, trainer_id, secret_id, max(1, self.panel.max_advance() - base), species, options["nature"], base, bot.options.target_level
            )
        except EmulatorError as error:
            app.set_status(f"Could not list the Pokémon: {error}", "error")
            return
        self.panel.set_targets(rows, bot.options.rows_note)
        self.panel.set_status("")
        app.set_status(f"{len(rows)} shiny Pokémon listed, advances counted from the start of the game (now at {base:,}). The game is paused.", "success")

    def _with_boot_seed(self, options: dict) -> dict:
        game = self.app.game
        return {**options, "boot_seed": game.boot_seed()} if hasattr(game, "boot_seed") else options

    def start_listing(self, bot, options: dict) -> None:
        app = self.app
        self.bot = bot
        app.emulator.set_fixed_clock(RELOAD_CLOCK)
        options = self._with_boot_seed(options)
        self._start_process(
            run_list,
            (str(app.rom), app.emulator.get_state(), bot.options.name, options, self.panel.max_advance(), self._new_queue(), RELOAD_CLOCK, self.save_bytes()),
        )
        self.state = "listing"
        self.panel.set_running(True)
        self.panel.set_progress(None)
        self.panel.set_status(f"{bot.options.name}: listing the shiny Pokémon (the bot plays its start first) ...", P.accent)
        app.set_status(f"Listing the shiny Pokémon for {bot.options.name}.")
        app.window.after(POLL_MS, self.poll)


    def start_bot(self, options: dict) -> None:
        app = self.app
        if self.state is not None:
            return
        if app.cheats.is_on():
            self.refuse("Cheats are on. Turn them off first (Emulation > Cheats...): a bot needs the unchanged game.")
            return
        bot = bots_for(app.game)[options["mode"]]
        chosen = self.panel.selected_targets() if bot.options.supports_targets else []
        if bot.options.supports_targets or bot.options.saves_first:
            problem = bot.problem(app.game)
            if problem is not None:
                self.refuse(problem)
                return
            if chosen:
                if bot.options.advances_from_boot and not app.files.reload_game():
                    return
            elif not app.files.save_game():
                return
        if app.loop.user_paused:
            app.loop.toggle_pause()
        start_base = app.game.advances() if chosen and bot.options.advances_from_boot else 0
        options = {
            **options,
            "targets": chosen,
            "target_advances": self.panel.selected_advances() if chosen else [],
            "target_limit": max(MIN_TARGET_LIMIT, self.panel.selected_max_advance() - start_base) + TARGET_LIMIT_MARGIN,
        }
        self.start_hunt(bot, options)

    def start_hunt(self, bot, options: dict) -> None:
        app = self.app
        problem = bot.problem(app.game)
        if problem is not None:
            self.refuse(problem)
            return

        self.panel.set_result("")
        self.bot = bot
        nature = options["nature"]
        frozen_clock = RELOAD_CLOCK if options.get("targets") else datetime.datetime.now()
        app.emulator.set_fixed_clock(frozen_clock)
        self._start_process(run_hunt, (str(app.rom), app.emulator.get_state(), bot.options.name, self._with_boot_seed(options), self._new_queue(), frozen_clock, self.save_bytes()))
        self.state = "hunting"
        self.panel.set_running(True)
        self.panel.set_progress(None)
        what = bot.goal(options)
        what += f" with {'an' if nature[0].lower() in 'aeiou' else 'a'} {nature} nature" if nature else ""
        self.panel.set_status(f"{bot.options.name}: searching for {what} ...", P.accent)
        app.set_status(f"Bot ({bot.options.name}): searching for {what}.")
        app.window.after(POLL_MS, self.poll)

    def _new_queue(self):
        self.queue = multiprocessing.get_context("spawn").Queue()
        return self.queue

    def _start_process(self, target, arguments: tuple) -> None:
        self.process = multiprocessing.get_context("spawn").Process(target=target, args=arguments, daemon=False)
        self.process.start()


    def poll(self) -> None:
        if self.state not in ("hunting", "listing"):
            return
        listing = self.state == "listing"
        process_has_ended = not self.process.is_alive()
        received_something = False
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                received_something = True
                if kind == "log":
                    self.panel.set_status(f"{self.bot.options.name}: {payload.strip()}", P.accent)
                    continue
                if kind == "done":
                    self.begin_replay(payload)
                    return
                if kind == "table":
                    self.end("", "info")
                    self.panel.set_targets(payload, self.bot.options.rows_note)
                    self.panel.set_status("")
                    self.app.set_status(f"{len(payload)} shiny Pokémon listed. The game is paused.", "success")
                    return
                if kind == "fail":
                    self.end(f"Could not list the Pokémon: {payload}" if listing else f"Failed: {payload}", "error")
                    return
        except queue.Empty:
            pass
        if process_has_ended and not received_something:
            self.end("The listing process stopped unexpectedly." if listing else "The search process stopped unexpectedly.", "error")
            return
        self.app.window.after(POLL_MS, self.poll)

    def begin_replay(self, plan: dict) -> None:
        self.plan = plan
        self.process.join(timeout=2)
        self.process = None
        self.replay = expand(plan["keys"])
        self.replay_writes = writes_by_frame(plan.get("writes", []))
        self.replay_frames = 0
        self.state = "replaying"
        self.panel.set_progress(0.0)
        self.panel.set_status("Replaying the plan in the game ...", P.accent)
        self.app.set_status("Bot: replaying the plan in the game.")
        self.app.loop.restart_clock()

    def next_replay_keys(self) -> int | None:
        apply_writes(self.app.emulator, self.replay_writes.get(self.replay_frames, []))
        try:
            keys = next(self.replay)
        except StopIteration:
            pokemon = self.bot.result(self.app.game, self.plan)
            matches = pokemon.personality_value == self.plan["pid"]
            note = "" if matches else "  (but not the Pokémon the search predicted!)"
            self.end(f"Done: {pokemon.describe()}{note}", "success" if matches else "error", pokemon)
            return None
        self.replay_frames += 1
        return keys

    def replay_progress(self) -> float:
        return self.replay_frames / max(1, self.plan["frames"])


    def stop_bot(self) -> None:
        if self.state is not None:
            self.end("Stopped.", "warning")

    def end(self, status: str, level: str = "info", pokemon: PartyPokemon | None = None) -> None:
        if self.process is not None:
            if self.process.is_alive():
                stop_process_tree(self.process)
            self.process.join(timeout=2)
            if hasattr(self.process, "cleanup"):
                self.process.cleanup()
            self.process = None
        self.state = None
        self.replay = None
        self.app.emulator.use_real_clock()
        self.app.reset_inputs()
        self.panel.set_running(False)
        if pokemon is not None:
            self.panel.set_status("Done.", P.success if level == "success" else P.danger)
            self.panel.set_result(pokemon.describe(), pokemon.is_shiny)
            if level == "success":
                self.panel.set_progress(1.0)
        else:
            self.panel.set_status(status, STATUS_COLORS.get(level, P.text))
        self.app.set_status(status, level)

    def shut_down(self) -> None:
        if self.process is not None and self.process.is_alive():
            stop_process_tree(self.process)
