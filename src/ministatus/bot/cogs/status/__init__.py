from ministatus.bot.bot import Bot

from .cog import StatusCog


async def setup(bot: Bot) -> None:
    await bot.add_cog(StatusCog(bot))
