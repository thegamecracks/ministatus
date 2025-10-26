import datetime
import logging

import discord
from discord.ext import commands, tasks

from ministatus.bot.bot import Bot
from ministatus.db import connect

log = logging.getLogger(__name__)


class Cleanup(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.cleanup_loop.start()

    # @commands.Cog.listener("on_guild_remove")
    # async def remove_guild(self, guild: discord.Guild):
    #     async with self.bot.acquire_db_conn() as conn:
    #         await conn.execute("DELETE FROM discord_guild WHERE guild_id = ?", guild.id)
    #
    # In case the bot is unintentionally kicked, retain all data
    # until the next cleanup cycle

    @commands.Cog.listener("on_guild_channel_delete")
    async def remove_guild_channel(self, channel: discord.abc.GuildChannel) -> None:
        async with connect() as conn:
            await conn.execute(
                "DELETE FROM discord_channel WHERE channel_id = $1",
                channel.id,
            )

    @commands.Cog.listener("on_raw_thread_delete")
    async def remove_thread(self, payload: discord.RawThreadDeleteEvent) -> None:
        async with connect() as conn:
            await conn.execute(
                "DELETE FROM discord_channel WHERE channel_id = $1",
                payload.thread_id,
            )

    @commands.Cog.listener("on_raw_message_delete")
    async def remove_message(self, payload: discord.RawMessageDeleteEvent):
        async with connect() as conn:
            await conn.execute(
                "DELETE FROM discord_message WHERE message_id = $1",
                payload.message_id,
            )

    @commands.Cog.listener("on_raw_bulk_message_delete")
    async def bulk_remove_messages(self, payload: discord.RawBulkMessageDeleteEvent):
        mid = ", ".join("?" * len(payload.message_ids))
        async with connect() as conn:
            await conn.execute(
                f"DELETE FROM message WHERE id IN ({mid})",
                *payload.message_ids,
            )

    # NOTE: members intent required
    @commands.Cog.listener("on_raw_member_remove")
    async def remove_member(self, payload: discord.RawMemberRemoveEvent) -> None:
        async with connect() as conn:
            await conn.execute(
                "DELETE FROM discord_member WHERE guild_id = $1 AND user_id = $2",
                payload.guild_id,
                payload.user.id,
            )

    @tasks.loop(time=datetime.time(0, 0, tzinfo=datetime.timezone.utc))
    async def cleanup_loop(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        if now.weekday() != 6:
            return

        await self.cleanup_guilds()

    async def cleanup_guilds(self) -> None:
        # NOTE: this is incompatible with sharding
        guild_ids = {guild.id for guild in self.bot.guilds}
        async with connect() as conn:
            rows = await conn.fetch("SELECT guild_id FROM discord_guild")
            rows = {row[0] for row in rows}
            deleted = rows - guild_ids
            for guild_id in deleted:
                await conn.execute(
                    "DELETE FROM discord_guild WHERE guild_id = $1",
                    guild_id,
                )

        if len(rows) > 0:
            log.info("%d guilds cleaned up", len(rows))

    # NOTE: Discord users are not removed by any event
    # NOTE: rows can still accumulate during bot downtime


async def setup(bot: Bot):
    await bot.add_cog(Cleanup(bot))
