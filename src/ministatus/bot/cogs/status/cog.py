import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ministatus.bot.bot import Bot
from ministatus.bot.db import connect_discord_database_client
from ministatus.db import connect_client

from .query import run_query_jobs
from .views import StatusManageView, display_cache

DEFAULT_QUERY_INTERVAL = 60

log = logging.getLogger(__name__)


@app_commands.allowed_contexts(guilds=True)
@app_commands.allowed_installs(guilds=True)
@app_commands.default_permissions(manage_guild=True)
class StatusCog(
    commands.GroupCog,
    group_name="status",
    group_description="Manage server statuses.",
):
    query_interval: int

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

        self.query_loop.add_exception_type(
            discord.DiscordServerError,
            discord.RateLimited,
        )

    async def cog_load(self) -> None:
        await self._set_query_interval()
        self.query_loop.start()

    async def cog_unload(self) -> None:
        self.query_loop.cancel()
        for view in display_cache.values():
            view.stop()

    @app_commands.command(name="manage")
    async def status_manage(self, interaction: discord.Interaction[Bot]) -> None:
        """Manage your server statuses."""
        assert interaction.guild is not None
        assert isinstance(interaction.user, discord.Member)

        guild_id = interaction.guild.id
        async with connect_discord_database_client(self.bot) as ddc:
            await ddc.add_member(interaction.user)
            statuses = await ddc.client.get_bulk_statuses_by_guilds(
                guild_id,
                with_relationships=True,
            )

        view = StatusManageView(interaction, statuses)
        await view.send(interaction, ephemeral=True)

    @tasks.loop(seconds=60)
    async def query_loop(self) -> None:
        await run_query_jobs(self.bot)

    @query_loop.before_loop
    async def query_before_loop(self) -> None:
        delay = self.query_interval - time.time() % self.query_interval
        log.info("Waiting %.2fs before starting query loop...", delay)
        await asyncio.sleep(delay)

    async def _set_query_interval(self) -> None:
        async with connect_client() as client:
            query_interval = await client.get_setting("status-interval")
            if query_interval is None:
                query_interval = DEFAULT_QUERY_INTERVAL
                await client.set_setting("status-interval", query_interval)

        query_interval = int(query_interval)
        if query_interval < 30:
            log.warning(
                "status-interval (%ds) is too short, defaulting to %ds",
                query_interval,
                DEFAULT_QUERY_INTERVAL,
            )
            query_interval = DEFAULT_QUERY_INTERVAL

        self.query_interval = query_interval
        self.query_loop.change_interval(seconds=query_interval)
