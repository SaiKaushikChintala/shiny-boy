import time
import zlib
from array import array
from typing import Callable

from shiny.core.emulator.interface import EmulatorInterface
from shiny.core.rng import lcrng

SNAPSHOT_EVERY = 8192


class WaitTable:
    def __init__(
        self,
        emulator: EmulatorInterface,
        rng_address: int,
        start_state: bytes,
        progress: Callable[[int, int, float], None] | None = None,
        snapshot_every: int = SNAPSHOT_EVERY,
    ):
        self.emulator = emulator
        self.progress = progress
        self.snapshot_every = snapshot_every
        self._rng_address = rng_address

        emulator.set_state(start_state)
        self.start_rng = emulator.read_u32(rng_address)

        self.advances = array("I", [0])
        self._snapshots: dict[int, bytes] = {0: zlib.compress(start_state, 1)}

    @property
    def last_delay(self) -> int:
        return len(self.advances) - 1

    def state_after(self, delay: int) -> bytes:
        resume = max(d for d in self._snapshots if d <= delay)
        self.emulator.set_state(zlib.decompress(self._snapshots[resume]))
        self.emulator.set_keys(0)
        for _ in range(delay - resume):
            self.emulator.run_frame()
        return self.emulator.get_state()

    def walk(self, first: int, last: int):
        emulator = self.emulator
        state = self.state_after(first)
        for delay in range(first, last + 1):
            emulator.set_state(state)
            emulator.set_keys(0)
            yield delay
            if delay < last:
                emulator.set_state(state)
                emulator.set_keys(0)
                emulator.run_frame()
                state = emulator.get_state()

    def extend_to(self, delay: int) -> None:
        if delay <= self.last_delay:
            return

        emulator = self.emulator
        run_frame = emulator.run_frame
        read_u32 = emulator.read_u32
        address = self._rng_address
        next_state = lcrng.next_state

        self.state_after(self.last_delay)
        previous = read_u32(address)
        total = self.advances[-1]
        began = time.perf_counter()
        began_at = self.last_delay

        for current_delay in range(self.last_delay + 1, delay + 1):
            run_frame()
            current = read_u32(address)
            steps = 0
            probe = previous
            while probe != current and steps < 64:
                probe = next_state(probe)
                steps += 1
            if probe != current:
                steps = lcrng.distance(previous, current)
            total += steps
            self.advances.append(total)
            previous = current

            if current_delay % self.snapshot_every == 0:
                self._snapshots[current_delay] = zlib.compress(emulator.get_state(), 1)
                if self.progress is not None:
                    speed = (current_delay - began_at) / max(time.perf_counter() - began, 1e-9)
                    self.progress(current_delay, total, speed)
