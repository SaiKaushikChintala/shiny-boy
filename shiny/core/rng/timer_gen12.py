SHINY_ATTACK_DVS = (2, 3, 6, 7, 10, 11, 14, 15)
SHINY_OTHER_DV = 10


def split_dvs(dv_bytes: tuple[int, int]) -> tuple[int, int, int, int]:
    return dv_bytes[0] >> 4, dv_bytes[0] & 15, dv_bytes[1] >> 4, dv_bytes[1] & 15


def is_shiny(dv_bytes: tuple[int, int]) -> bool:
    attack, defense, speed, special = split_dvs(dv_bytes)
    return defense == speed == special == SHINY_OTHER_DV and attack in SHINY_ATTACK_DVS
