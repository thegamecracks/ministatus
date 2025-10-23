from ministatus.bot.bot import Bot

from .cog import Status


async def setup(bot: Bot) -> None:
    await bot.add_cog(Status(bot))
