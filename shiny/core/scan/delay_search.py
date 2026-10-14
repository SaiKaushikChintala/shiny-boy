import multiprocessing
import time
from typing import Callable

DEFAULT_BLOCK = 2000

_hunter = None


def _prepare(builder: Callable[[], object]) -> None:
    global _hunter
    _hunter = builder()


def _scan_block(block: tuple[int, int]) -> list:
    return _hunter.scan(*block)


def find_first_hit(
    builder: Callable[[], object], max_delay: int, workers: int, log: Callable[[str], None], block: int = DEFAULT_BLOCK
) -> tuple | None:
    blocks = [(first, min(first + block, max_delay)) for first in range(0, max_delay, block)]
    started = time.time()
    with multiprocessing.get_context("spawn").Pool(workers, _prepare, (builder,)) as pool:
        for done, hits in enumerate(pool.imap(_scan_block, blocks), 1):
            if hits:
                pool.terminate()
                return hits[0]
            if done % workers == 0:
                log(f"  nothing in the first {blocks[done - 1][1]:,} delays ({time.time() - started:.0f}s)")
    return None
