from dataclasses import dataclass

from shiny.core.rng.timer_gen12 import is_shiny, split_dvs


@dataclass(frozen=True)
class GbPokemon:
    species: int
    species_name: str
    dv_bytes: tuple[int, int]
    generation: int = 2

    @property
    def personality_value(self) -> int:
        return self.dv_bytes[0] << 8 | self.dv_bytes[1]

    @property
    def is_shiny(self) -> bool:
        return is_shiny(self.dv_bytes)

    def describe(self) -> str:
        attack, defense, speed, special = split_dvs(self.dv_bytes)
        shiny = "SHINY " if self.is_shiny and self.generation == 2 else ""
        note = "  (shiny once traded to Gen 2)" if self.is_shiny and self.generation == 1 else ""
        return f"{shiny}{self.species_name}  DVs {self.dv_bytes[0]:02x}{self.dv_bytes[1]:02x}  (Atk {attack} Def {defense} Spe {speed} Spc {special}){note}"
