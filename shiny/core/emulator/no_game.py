import datetime
from pathlib import Path

from shiny.core.emulator.interface import EmulatorError
from shiny.paths import ROMS_DIRECTORY

WIDTH, HEIGHT = 240, 160
NO_GAME_ROM = ROMS_DIRECTORY / "(no game)"
OPEN_FIRST = "Open a ROM first (File > Load ROM, or Ctrl+O)."


class NoGame:

    placeholder = True
    title = "Shiny Boy"
    code = ""
    is_gba = False
    frame_count = 0
    resolution = (WIDTH, HEIGHT)
    rom_path = NO_GAME_ROM

    def frame_bgrx(self) -> bytes:
        return bytes(WIDTH * HEIGHT * 4)

    def run_frame(self) -> None:
        pass

    def run_frames(self, count: int) -> None:
        pass

    def reset(self) -> None:
        pass

    def set_keys(self, mask: int) -> None:
        pass

    def read_audio(self) -> bytes:
        return b""

    def set_audio_rate(self, sample_rate: int) -> None:
        pass

    def set_video_enabled(self, enabled: bool) -> None:
        pass

    def set_fixed_clock(self, when: datetime.datetime) -> None:
        pass

    def use_real_clock(self) -> None:
        pass

    def get_state(self) -> bytes:
        return b""

    def set_state(self, state: bytes) -> None:
        raise EmulatorError(OPEN_FIRST)

    def load_state_file(self, path: str | Path) -> None:
        raise EmulatorError(OPEN_FIRST)

    def save_state_file(self, path: str | Path) -> None:
        raise EmulatorError(OPEN_FIRST)

    def load_save_file(self, save_path: str | Path) -> None:
        raise EmulatorError(OPEN_FIRST)

    def screenshot(self, path: str | Path) -> None:
        raise EmulatorError(OPEN_FIRST)
