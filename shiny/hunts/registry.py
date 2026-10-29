from shiny.hunts.base import Bot
from shiny.hunts.breeding.hunt import BreedingBot
from shiny.hunts.fishing.hunt import FishingBot
from shiny.hunts.gen1.static.hunt import Gen1TargetBot
from shiny.hunts.gen2.beast.hunt import BeastBot
from shiny.hunts.gen2.static.hunt import Gen2TargetBot
from shiny.hunts.gift.menu import Gen3GiftBot
from shiny.hunts.grass.hunt import GrassBot
from shiny.hunts.roamer.hunt import RoamerBot
from shiny.hunts.rock_smash.hunt import RockSmashBot
from shiny.hunts.static.hunt import StaticBot
from shiny.hunts.sweet_scent.hunt import SweetScentBot

BOTS_BY_GAME: dict[str, dict[str, Bot]] = {
    game: {bot.options.name: bot for bot in bots}
    for game, bots in {
        "ruby": (Gen3GiftBot("ruby"), StaticBot(), FishingBot(), SweetScentBot(), GrassBot(), RockSmashBot(), RoamerBot("ruby"), BreedingBot("ruby")),
        "sapphire": (Gen3GiftBot("sapphire"), StaticBot(), FishingBot(), SweetScentBot(), GrassBot(), RockSmashBot(), RoamerBot("sapphire"), BreedingBot("sapphire")),
        "firered": (Gen3GiftBot("firered"), StaticBot(), FishingBot(), SweetScentBot(), GrassBot(), RoamerBot("firered"), BreedingBot("firered")),
        "leafgreen": (Gen3GiftBot("leafgreen"), StaticBot(), FishingBot(), SweetScentBot(), GrassBot(), RoamerBot("leafgreen"), BreedingBot("leafgreen")),
        "emerald": (Gen3GiftBot("emerald"), StaticBot(), FishingBot(), SweetScentBot(), GrassBot(), RockSmashBot(), RoamerBot("emerald"), BreedingBot("emerald")),
        "red": (Gen1TargetBot("red", "gift"), Gen1TargetBot("red", "static")),
        "blue": (Gen1TargetBot("blue", "gift"), Gen1TargetBot("blue", "static")),
        "yellow": (Gen1TargetBot("yellow", "gift"), Gen1TargetBot("yellow", "static")),
        "gold": (Gen2TargetBot("gold", "gift"), Gen2TargetBot("gold", "static"), BeastBot("gold")),
        "silver": (Gen2TargetBot("silver", "gift"), Gen2TargetBot("silver", "static"), BeastBot("silver")),
        "crystal": (Gen2TargetBot("crystal", "gift"), Gen2TargetBot("crystal", "static"), BeastBot("crystal")),
    }.items()
}


def bots_for(game) -> dict[str, Bot]:
    return BOTS_BY_GAME.get(getattr(game, "key", None), {})
