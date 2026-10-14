SHINY_LIMIT = 8


def shiny_value(pid: int, trainer_id: int, secret_id: int) -> int:
    return trainer_id ^ secret_id ^ (pid >> 16) ^ (pid & 0xFFFF)


def is_shiny(pid: int, trainer_id: int, secret_id: int) -> bool:
    return shiny_value(pid, trainer_id, secret_id) < SHINY_LIMIT
