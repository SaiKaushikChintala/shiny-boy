import datetime
import sys
import zipfile
import zlib
from pathlib import Path
import PIL.PngImagePlugin

from shiny.core.emulator.interface import EmulatorError
from shiny.paths import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mgba.core
import mgba.image
import mgba.rng
import mgba.vfs


SGB_SCREEN_X, SGB_SCREEN_Y = 48, 40


class Emulator:
    def __init__(self, rom_path: str | Path, save_path: str | Path | None = None):
        rom_path = Path(rom_path)
        if not rom_path.is_file():
            raise EmulatorError(f"ROM not found: {rom_path}")

        self.rom_path = rom_path
        self.fixed_clock: datetime.datetime | None = None
        self._keys = 0
        self._recording: list[int] | None = None
        mgba.rng.silence_logs()

        self._core = mgba.core.load_path(str(rom_path))
        if not self._core:
            raise EmulatorError(f"mGBA could not load ROM: {rom_path}")

        self._save_file = None
        self.save_data: bytes | None = None
        if save_path is not None:
            self._attach_save_file(Path(save_path))

        super_game_boy = not self.is_gba and self._is_super_game_boy_only(rom_path)
        dimensions = self._core.desired_video_dimensions() if self.is_gba or super_game_boy else (160, 144)
        self._visible = (SGB_SCREEN_X, SGB_SCREEN_Y, SGB_SCREEN_X + 160, SGB_SCREEN_Y + 144) if super_game_boy else None
        self._screen = mgba.image.Image(*dimensions)
        if not self.is_gba and dimensions == (160, 144):
            width, height = self._core.desired_video_dimensions()
            self._screen.stride = width
            self._screen.buffer = mgba.image.ffi.new("mColor[]", width * height)
        self._core.set_video_buffer(self._screen)
        self._core.reset()
        self._helpers = mgba.rng.Helpers(self._core)

    @staticmethod
    def _is_super_game_boy_only(rom_path) -> bool:
        suffix = Path(rom_path).suffix.lower()
        try:
            if zipfile.is_zipfile(rom_path):
                with zipfile.ZipFile(rom_path) as archive:
                    name = next((name for name in archive.namelist() if Path(name).suffix.lower() in (".gb", ".sgb", ".gbc", ".gba")), None)
                    if name is None:
                        return False
                    suffix = Path(name).suffix.lower()
                    with archive.open(name) as file:
                        header = file.read(0x150)
            else:
                with open(rom_path, "rb") as file:
                    header = file.read(0x150)
        except (OSError, zipfile.BadZipFile):
            return False
        return len(header) >= 0x150 and header[0x146] == 3 and not header[0x143] & 0x80 and suffix in (".gb", ".sgb")

    def _attach_save_file(self, save_path: Path) -> None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        if not save_path.exists():
            save_path.touch()
        self.save_data = save_path.read_bytes()
        save_file = mgba.vfs.open_path(str(save_path), "r+")
        if not save_file or not self._core.load_save(save_file):
            raise EmulatorError(f"mGBA could not use save file: {save_path}")
        self._save_file = save_file

    def load_save_file(self, save_path: str | Path) -> None:
        self._attach_save_file(Path(save_path))
        self._core.reset()

    def set_fixed_clock(self, when: datetime.datetime) -> None:
        self._helpers.use_fixed_clock(when)
        self.fixed_clock = when

    def use_real_clock(self) -> None:
        self._helpers.use_real_clock()
        self.fixed_clock = None

    def get_state(self) -> bytes:
        return self._helpers.save_state()

    def set_state(self, state: bytes) -> None:
        try:
            self._helpers.load_state(state)
        except mgba.rng.RngError as error:
            raise EmulatorError(f"mGBA could not load this save state ({error}).") from error

    def save_state_file(self, path: str | Path) -> None:
        extra_chunks = PIL.PngImagePlugin.PngInfo()
        extra_chunks.add(b"gbAs", zlib.compress(self.get_state()))
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as file:
            self.current_image().save(file, format="PNG", pnginfo=extra_chunks)

    def load_state_file(self, path: str | Path) -> None:
        self.set_state(Path(path).read_bytes())

    @property
    def is_gba(self) -> bool:
        return self._core.platform == mgba.core.Core.PLATFORM_GBA

    @property
    def native_core(self):
        return self._core._core

    @property
    def title(self) -> str:
        return self._core.game_title

    @property
    def code(self) -> str:
        return self._core.game_code

    @property
    def frame_count(self) -> int:
        return self._core.frame_counter

    @property
    def resolution(self) -> tuple[int, int]:
        if self._visible:
            return 160, 144
        return self._screen.width, self._screen.height

    def reset(self) -> None:
        self._core.reset()

    def run_frame(self) -> None:
        if self._recording is not None:
            self._recording.append(self._keys)
        self._core.run_frame()

    def run_frames(self, count: int) -> None:
        if self._recording is not None:
            self._recording.extend([self._keys] * count)
        self._helpers.run_frames(count, held=self._keys)

    def start_recording(self) -> None:
        self._recording = []

    def stop_recording(self) -> list[int]:
        keys, self._recording = (self._recording or []), None
        return keys

    def read_bytes(self, address: int, length: int = 1, bank: int | None = None) -> bytes:
        try:
            return self._helpers.read(address, length, bank)
        except mgba.rng.RngError as error:
            raise EmulatorError(f"Cannot read from address {address:#x} ({error})") from error

    def read_u8(self, address: int, bank: int | None = None) -> int:
        if bank is None and not self.is_gba:
            return self._core.memory.u8[address]
        return self.read_bytes(address, 1, bank)[0]

    def read_u32(self, address: int) -> int:
        return int.from_bytes(self.read_bytes(address, 4), "little")

    def write_rom(self, address: int, data: bytes) -> None:
        if self.is_gba and address >> 24 < 0x8:
            raise EmulatorError(f"Not a ROM address: {address:#x}")
        try:
            self._helpers.write_rom(address, bytes(data))
        except mgba.rng.RngError as error:
            raise EmulatorError(f"Cannot write to ROM address {address:#x} ({error})") from error

    def write_bytes(self, address: int, data: bytes, bank: int | None = None) -> None:
        try:
            self._helpers.write(address, bytes(data), bank)
        except mgba.rng.RngError as error:
            raise EmulatorError(f"Cannot write to address {address:#x} ({error})") from error

    def set_video_enabled(self, enabled: bool) -> None:
        self._helpers.set_video_enabled(enabled)

    def set_audio_rate(self, sample_rate: int) -> None:
        self._helpers.set_audio_rate(sample_rate)

    def read_audio(self) -> bytes:
        return self._helpers.read_audio()

    def set_keys(self, mask: int) -> None:
        self._keys = mask
        self._core.set_keys(raw=mask)

    def current_image(self):
        image = self._screen.to_pil()
        return (image.crop(self._visible) if self._visible else image).convert("RGB")

    def frame_bgrx(self) -> bytes:
        return self._screen.to_pil().crop(self._visible or (0, 0, *self.resolution)).tobytes("raw", "BGRX")

    def screenshot(self, path: str | Path) -> None:
        self.current_image().save(path, format="PNG")
