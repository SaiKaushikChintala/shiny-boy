import struct
from dataclasses import dataclass

from shiny.core.pokemon.natures import NATURE_COUNT, NATURES
from shiny.core.pokemon.species import gen3_name
from shiny.core.rng.shiny_rule import is_shiny

PARTY_POKEMON_SIZE = 100

SUBSTRUCTURE_ORDER = [
    (0, 1, 2, 3), (0, 1, 3, 2), (0, 2, 1, 3), (0, 3, 1, 2), (0, 2, 3, 1), (0, 3, 2, 1),
    (1, 0, 2, 3), (1, 0, 3, 2), (2, 0, 1, 3), (3, 0, 1, 2), (2, 0, 3, 1), (3, 0, 2, 1),
    (1, 2, 0, 3), (1, 3, 0, 2), (2, 1, 0, 3), (3, 1, 0, 2), (2, 3, 0, 1), (3, 2, 0, 1),
    (1, 2, 3, 0), (1, 3, 2, 0), (2, 1, 3, 0), (3, 1, 2, 0), (2, 3, 1, 0), (3, 2, 1, 0),
]


@dataclass
class PartyPokemon:
    personality_value: int
    trainer_id: int
    secret_id: int
    species: int
    iv_word: int
    checksum_is_valid: bool

    @property
    def species_name(self) -> str:
        return gen3_name(self.species)

    @property
    def nature(self) -> str:
        return NATURES[self.personality_value % NATURE_COUNT]

    @property
    def ivs(self) -> dict[str, int]:
        return {
            "HP": self.iv_word & 31,
            "Atk": (self.iv_word >> 5) & 31,
            "Def": (self.iv_word >> 10) & 31,
            "Spe": (self.iv_word >> 15) & 31,
            "SpA": (self.iv_word >> 20) & 31,
            "SpD": (self.iv_word >> 25) & 31,
        }

    @property
    def is_shiny(self) -> bool:
        return is_shiny(self.personality_value, self.trainer_id, self.secret_id)

    def describe(self) -> str:
        ivs = " ".join(f"{name} {value}" for name, value in self.ivs.items())
        shiny = "SHINY " if self.is_shiny else ""
        return f"{shiny}{self.species_name}  PID {self.personality_value:#010x}  {self.nature}  IVs: {ivs}"


def parse_party_pokemon(data: bytes) -> PartyPokemon:
    personality_value, ot_id = struct.unpack_from("<II", data, 0)
    order = SUBSTRUCTURE_ORDER[personality_value % 24]
    stored_checksum = struct.unpack_from("<H", data, 28)[0]

    def read(key: int):
        blocks = []
        for position in range(4):
            offset = 32 + order[position] * 12
            words = struct.unpack_from("<3I", data, offset)
            blocks.append(struct.pack("<3I", *(word ^ key for word in words)))
        valid = (sum(struct.unpack("<24H", b"".join(blocks))) & 0xFFFF) == stored_checksum
        return blocks, valid

    blocks, valid = read(personality_value ^ ot_id)
    if not valid:
        plain_blocks, plain_valid = read(0)
        if plain_valid:
            blocks, valid = plain_blocks, True

    growth, _attacks, _evs, misc = blocks
    species = struct.unpack_from("<H", growth, 0)[0]
    iv_word = struct.unpack_from("<I", misc, 4)[0] & 0x3FFFFFFF

    return PartyPokemon(
        personality_value=personality_value,
        trainer_id=ot_id & 0xFFFF,
        secret_id=ot_id >> 16,
        species=species,
        iv_word=iv_word,
        checksum_is_valid=valid,
    )
