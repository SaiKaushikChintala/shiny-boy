from typing import Iterator

from shiny.core.emulator.interface import EmulatorInterface


def compress(keys: list[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    for key in keys:
        if runs and runs[-1][0] == key:
            runs[-1][1] += 1
        else:
            runs.append([key, 1])
    return runs


def expand(runs: list[list[int]]) -> Iterator[int]:
    for key, count in runs:
        for _ in range(count):
            yield key


def writes_by_frame(writes: list[list]) -> dict[int, list[tuple[str, int, bytes]]]:
    by_frame: dict[int, list[tuple[str, int, bytes]]] = {}
    for frame, kind, address, data in writes:
        by_frame.setdefault(frame, []).append((kind, address, bytes.fromhex(data)))
    return by_frame


def apply_writes(emu: EmulatorInterface, writes: list[tuple[str, int, bytes]]) -> None:
    for kind, address, data in writes:
        if kind == "rom":
            emu.write_rom(address, data)
        else:
            emu.write_bytes(address, data)


def play_keys(emu: EmulatorInterface, start_state: bytes, keys: list[int], writes: list[list] | None = None) -> None:
    emu.set_state(start_state)
    pending = writes_by_frame(writes or [])
    for frame, key in enumerate(keys):
        apply_writes(emu, pending.get(frame, []))
        emu.set_keys(key)
        emu.run_frame()
    apply_writes(emu, pending.get(len(keys), []))
