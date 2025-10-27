import discord
from discord.ext import commands

from ministatus.bot.bot import Bot, Context


class Owner(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: Context):  # type: ignore  # async is allowed
        return await commands.is_owner().predicate(ctx)

    @commands.command()
    async def sync(self, ctx: Context, guild_id: int | None = None):
        """Synchronize the bot's application commands."""
        guild = discord.Object(guild_id) if guild_id else None
        commands = await ctx.bot.tree.sync(guild=guild)
        n_commands = len(commands)
        await ctx.send(f"{n_commands} command(s) synchronized!")


async def setup(bot: Bot):
    await bot.add_cog(Owner(bot))
