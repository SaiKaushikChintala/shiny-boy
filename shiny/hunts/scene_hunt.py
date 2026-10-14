from typing import Callable

from shiny.core.emulator.buttons import Button
from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.pokemon.gb_model import GbPokemon
from shiny.core.scan.engine import ScriptFailed
from shiny.hunts.timer_hunt import TimerHunt

DOOR_FRAMES = 60
MENU_TRIES = 3000
PARTY_MON_DATA_FRAMES = 400
LEADS = (20, 40, 80, 130, 200, 300, 450, 700, 1000, 1500, 2500)
VARIETY_WAITS = range(3000, 3024)


class SceneHunt(TimerHunt):

    A_FRAMES_ON = 2
    A_PERIOD = 25
    BASELINE_TIMEOUT = 8000
    GIVE_TIMEOUT = 5000
    STABLE_FRAMES = 3
    SUBTRACT_STABLE = False
    ADJUST_TIMEOUT = False
    STATIC_SETTLE_FRAMES = 0
    NO_POKEMON_MESSAGE = "The scene could not be played from this state. Stand in front of the Pokémon (or of who gives it), facing it."

    def __init__(self, emu: EmulatorInterface, game, start_state: bytes, options: dict, log: Callable[[str], None] = print):
        self.spec = self.find_target(game.key, options["choice"])
        self.species = self.spec["species"]
        self.static = self.spec["kind"] == "static"
        self._streak = 0
        self.lead: int | None = options.get("lead")
        emu.set_state(start_state)
        self.party_before = game.party_size()
        super().__init__(emu, game, start_state, options, log)


    @staticmethod
    def load_targets(game: str) -> dict[str, dict]:
        raise NotImplementedError

    def menu_ready(self) -> bool:
        raise NotImplementedError

    def gift_made(self) -> bool:
        raise NotImplementedError

    def extra_scene(self, intro: str):
        return None


    @classmethod
    def find_target(cls, game: str, label: str) -> dict:
        for spec in cls.load_targets(game).values():
            if spec["label"] == label:
                return spec
        raise ScriptFailed(f"Unknown Pokémon: {label}")

    def _a_key(self, frame: int) -> int:
        if self.spec["intro"] == "door" and frame < DOOR_FRAMES:
            return Button.UP
        return super()._a_key(frame)

    def _press(self, key: int, frames: int = 2):
        for _ in range(frames):
            yield key

    def _wait(self, frames: int):
        for _ in range(frames):
            yield 0

    def _move_cursor(self, current: int, wanted: int):
        key = Button.DOWN if wanted > current else Button.UP
        for _ in range(abs(wanted - current)):
            yield from self._press(key)
            yield from self._wait(10)

    def _prize_scene(self):
        places = int(self.spec["intro"].split(":")[1])
        for frame in range(MENU_TRIES):
            if self.menu_ready():
                break
            yield self._a_key(frame)
        else:
            raise ScriptFailed("The prize menu did not come up.")
        yield from self.after_menu_comes(places)

    def after_menu_comes(self, places: int):
        raise NotImplementedError

    def _scene(self):
        intro = self.spec["intro"]
        if intro.startswith("prize"):
            yield from self._prize_scene()
        else:
            extra = self.extra_scene(intro)
            if extra is not None:
                yield from extra


    def choose_lead(self, start: bytes, scripted_until: int, made_at: int, given_after: int) -> int:
        if self.lead is None:
            if self.spec["intro"] == "door":
                self.lead = made_at - scripted_until
            else:
                self.lead = self._find_lead(start, scripted_until, made_at, given_after)
        return self.lead

    def _find_lead(self, start: bytes, scripted_until: int, made_at: int, given_after: int) -> int:
        leads = [lead for lead in LEADS if made_at - lead > scripted_until]
        leads.append(made_at - scripted_until)
        low, high, best = 0, len(leads) - 1, None
        while low <= high:
            middle = (low + high) // 2
            stop = min(max(scripted_until, made_at - leads[middle]), given_after - 1)
            snapshot, _keys = self._state_at(start, scripted_until, stop)
            if self._varies(snapshot):
                best, high = leads[middle], middle - 1
            else:
                low = middle + 1
        if best is None:
            raise ScriptFailed("Waiting does not change what is given: there is no moment in the scene to wait at.")
        return best

    def _varies(self, snapshot: bytes) -> bool:
        found = set()
        for delay in VARIETY_WAITS:
            self.emu.set_state(snapshot)
            self._run(0, delay)
            found.add(self.outcome())
        return len(found) >= self.spec.get("variety", 12)

    def worker_options(self) -> dict:
        return {**self.options, "lead": self.lead}

    def _given(self) -> bool:
        if self.static:
            if self.game.enemy_species() == self.species and self.game.in_battle():
                self._streak += 1
            else:
                self._streak = 0
            return self._streak >= self.STABLE_FRAMES
        return self.gift_made()

    def _take_snapshot(self) -> bytes:
        emu = self.emu
        emu.set_state(self.start_state)
        emu.start_recording()
        self._run(0, 1)
        first_frame = emu.stop_recording()
        start = emu.get_state()
        self._streak = 0
        scene = self._scene()
        scripted_until, given_after = None, None
        for frame in range(self.BASELINE_TIMEOUT):
            key = None
            if scripted_until is None:
                try:
                    key = next(scene)
                except StopIteration:
                    scripted_until = frame
            if key is None:
                key = self._a_key(frame - (scripted_until or 0))
            self._run(key, 1)
            if self._given():
                given_after = frame
                break
        if given_after is None:
            raise ScriptFailed(self.NO_POKEMON_MESSAGE)
        scripted_until = scripted_until or 0
        made_at = given_after - (self.STABLE_FRAMES if self.static and self.SUBTRACT_STABLE else 0)
        lead = self.choose_lead(start, scripted_until, made_at, given_after)
        stop = min(max(scripted_until, made_at - lead), given_after - 1)
        if self.ADJUST_TIMEOUT:
            self.GIVE_TIMEOUT = int((given_after - stop) * 1.25) + 100
        snapshot, keys = self._state_at(start, scripted_until, stop)
        self.prelude_keys = first_frame + keys
        return snapshot

    def _state_at(self, start: bytes, scripted_until: int, stop: int) -> tuple[bytes, list[int]]:
        self.emu.set_state(start)
        self._streak = 0
        scene = self._scene()
        self.emu.start_recording()
        for frame in range(stop):
            key = next(scene) if frame < scripted_until else None
            self._run(key if key is not None else self._a_key(frame - scripted_until), 1)
        keys = self.emu.stop_recording()
        return self.emu.get_state(), keys


    def outcome(self) -> GbPokemon | None:
        self._streak = 0
        for frame in range(self.GIVE_TIMEOUT):
            self._run(self._a_key(frame), 1)
            if self._given():
                if self.static:
                    self._run(0, self.STATIC_SETTLE_FRAMES)
                    return self.game.enemy_pokemon()
                return self.made_gift()
        return None

    def made_gift(self) -> GbPokemon:
        last = self.game.party_size() - 1
        for _ in range(PARTY_MON_DATA_FRAMES):
            self._run(0, 1)
            if self.game.party_pokemon_made(last):
                break
        self._run(0, 5)
        return self.game.party_pokemon(last)
