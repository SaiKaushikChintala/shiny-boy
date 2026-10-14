from shiny.hunts.base import Bot
from shiny.hunts.breeding.hunt import BreedingBot
from shiny.hunts.fishing.hunt import FishingBot
from shiny.hunts.fossil.hunt import FossilBot
from shiny.hunts.gift.hunt import GiftBot
from shiny.hunts.gen1.starter.hunt import Gen1StarterBot, YellowPikachuBot
from shiny.hunts.gen1.static.hunt import Gen1TargetBot
from shiny.hunts.gen2.beast.hunt import BeastBot
from shiny.hunts.gen2.starter.hunt import Gen2StarterBot
from shiny.hunts.gen2.static.hunt import Gen2TargetBot
from shiny.hunts.grass.hunt import GrassBot
from shiny.hunts.item_encounter.hunt import SudowoodoBot
from shiny.hunts.roamer.hunt import RoamerBot
from shiny.hunts.rock_smash.hunt import RockSmashBot
from shiny.hunts.starter.frlg import FrlgStarterBot
from shiny.hunts.starter.hunt import StarterBot
from shiny.hunts.static.hunt import StaticBot
from shiny.hunts.sweet_scent.hunt import SweetScentBot

BOTS_BY_GAME: dict[str, dict[str, Bot]] = {
    game: {bot.options.name: bot for bot in bots}
    for game, bots in {
        "ruby": (StarterBot(), FossilBot(), GiftBot(), StaticBot(), FishingBot(), SweetScentBot(), GrassBot(), RockSmashBot(), RoamerBot("ruby"), BreedingBot("ruby")),
        "sapphire": (StarterBot(), FossilBot(), GiftBot(), StaticBot(), FishingBot(), SweetScentBot(), GrassBot(), RockSmashBot(), RoamerBot("sapphire"), BreedingBot("sapphire")),
        "firered": (FrlgStarterBot(), GiftBot(), StaticBot(), FishingBot(), SweetScentBot(), GrassBot(), RoamerBot("firered"), BreedingBot("firered")),
        "leafgreen": (FrlgStarterBot(), GiftBot(), StaticBot(), FishingBot(), SweetScentBot(), GrassBot(), RoamerBot("leafgreen"), BreedingBot("leafgreen")),
        "emerald": (StarterBot(), FossilBot(), GiftBot(), StaticBot(), SudowoodoBot(), FishingBot(), SweetScentBot(), GrassBot(), RockSmashBot(), RoamerBot("emerald"), BreedingBot("emerald")),
        "red": (Gen1StarterBot(), Gen1TargetBot("red")),
        "blue": (Gen1StarterBot(), Gen1TargetBot("blue")),
        "yellow": (YellowPikachuBot(), Gen1TargetBot("yellow")),
        "gold": (Gen2StarterBot(), Gen2TargetBot("gold"), BeastBot("gold")),
        "silver": (Gen2StarterBot(), Gen2TargetBot("silver"), BeastBot("silver")),
        "crystal": (Gen2StarterBot(), Gen2TargetBot("crystal"), BeastBot("crystal")),
    }.items()
}


def bots_for(game) -> dict[str, Bot]:
    return BOTS_BY_GAME.get(getattr(game, "key", None), {})
