# Helpers of the RNG shiny bot project (see rng.c): the Python face of the functions written for this tree.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import datetime

from ._pylib import ffi, lib  # pylint: disable=no-name-in-module


RNG_OK = 0  # (the codes of rng.h; the pre-processing leaves no macros for cffi)


class RngError(Exception):
    pass


def silence_logs():
    lib.rngSilenceLogs()


class Helpers(object):
    """What the bot needs from a loaded `mgba.core.Core` and mGBA does not give: memory by bank, ROM patching, many frames in one call, ..."""

    def __init__(self, core):
        self._owner = core  # (keeps the core alive as long as we are)
        self._core = core._core
        self._audio = None

    # ----- frames -----

    def run_frames(self, count, held=0, keys=None):
        """Runs `count` frames holding the buttons `held`, or, with `keys` (a list with one mask for each frame), the masks of the list."""
        if keys is not None:
            count = len(keys)
            schedule = ffi.new("uint32_t[]", keys)
            return lib.rngRunFrames(self._core, schedule, 0, count)
        return lib.rngRunFrames(self._core, ffi.NULL, held, count)

    # ----- memory -----

    def read(self, address, length=1, bank=None):
        """GBA: EWRAM / IWRAM / ROM by its address on the bus. Game Boy: the address on its bus, from `bank` or the bank switched in."""
        out = ffi.new("uint8_t[]", length)
        if lib.rngRead(self._core, address, -1 if bank is None else bank, out, length) != RNG_OK:
            raise RngError("cannot read %d bytes at %#x" % (length, address))
        return bytes(ffi.buffer(out, length))

    def write(self, address, data, bank=None):
        if lib.rngWrite(self._core, address, -1 if bank is None else bank, data, len(data)) != RNG_OK:
            raise RngError("cannot write %d bytes at %#x" % (len(data), address))

    def read_rom(self, address, length=1):
        out = ffi.new("uint8_t[]", length)
        if lib.rngReadRom(self._core, address, out, length) != RNG_OK:
            raise RngError("cannot read %d bytes of ROM at %#x" % (length, address))
        return bytes(ffi.buffer(out, length))

    def write_rom(self, address, data):
        if lib.rngWriteRom(self._core, address, data, len(data)) != RNG_OK:
            raise RngError("cannot write %d bytes of ROM at %#x" % (len(data), address))

    # ----- picture -----

    def set_video_enabled(self, enabled):
        lib.rngSetVideoEnabled(self._core, bool(enabled))

    # ----- state -----

    def save_state(self):
        size = lib.rngStateSize(self._core)
        out = ffi.new("uint8_t[]", size)
        if lib.rngSaveState(self._core, out, size) != RNG_OK:
            raise RngError("the core could not save its state")
        return bytes(ffi.buffer(out, size))

    def load_state(self, state):
        """Raw state bytes, or the whole contents of a .ss1 file."""
        if lib.rngLoadState(self._core, state, len(state)) != RNG_OK:
            raise RngError("this state does not fit the game (wrong game, or a damaged file)")

    # ----- clock -----

    def use_fixed_clock(self, when):
        lib.rngClockFixed(self._core, round(when.timestamp() * 1000))

    def use_real_clock(self):
        lib.rngClockReal(self._core)

    # ----- sound -----

    def set_audio_rate(self, rate):
        if self._audio is not None:
            lib.rngAudioDestroy(self._audio)
        self._audio = lib.rngAudioCreate(self._core, rate)

    def read_audio(self):
        """The sound made since the last call, as stereo 16-bit PCM."""
        if self._audio is None:
            return b""
        count = lib.rngAudioAvailable(self._audio)
        if count <= 0:
            return b""
        out = ffi.new("int16_t[]", count * 2)
        count = lib.rngAudioRead(self._audio, out, count)
        return bytes(ffi.buffer(out, count * 4))

    def __del__(self):
        if getattr(self, "_audio", None) is not None:
            lib.rngAudioDestroy(self._audio)
            self._audio = None
