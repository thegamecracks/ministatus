import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ministatus.bot.bot import Bot
from ministatus.bot.db import connect_discord_database_client
from ministatus.db import fetch_statuses

from .query import run_query_jobs
from .views import StatusManageView, display_cache

log = logging.getLogger(__name__)


@app_commands.allowed_contexts(guilds=True)
@app_commands.allowed_installs(guilds=True)
@app_commands.default_permissions(manage_guild=True)
class StatusCog(
    commands.GroupCog,
    group_name="status",
    group_description="Manage server statuses.",
):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
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
            statuses = await fetch_statuses(
                ddc.client.conn,
                guild_ids=[guild_id],
                with_relationships=True,
            )

        view = StatusManageView(interaction, statuses)
        await view.send(interaction, ephemeral=True)

    @tasks.loop(seconds=60)
    async def query_loop(self) -> None:
        await run_query_jobs(self.bot)

    @query_loop.before_loop
    async def query_before_loop(self) -> None:
        delay = 60 - time.time() % 60
        log.info("Waiting %.2fs before starting query loop...", delay)
        await asyncio.sleep(delay)
