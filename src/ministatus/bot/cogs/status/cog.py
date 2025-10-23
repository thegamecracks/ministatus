import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ministatus.bot.bot import Bot
from ministatus.bot.db import connect_discord_database_client
from ministatus.db import Status, connect, fetch_statuses

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

    @app_commands.command(name="create")
    async def status_create(
        self,
        interaction: discord.Interaction[Bot],
        label: str,
    ) -> None:
        """Create a status entry.

        :param label: The label to assign to your status.

        """
        assert interaction.guild is not None
        assert isinstance(interaction.user, discord.Member)

        status = Status(status_id=0, guild_id=interaction.guild.id, label=label)
        async with connect_discord_database_client(self.bot) as ddc:
            await ddc.add_member(interaction.user)
            status = await ddc.client.create_status(status)

        message = f'Created status "{status.label}"!'
        await interaction.response.send_message(message, ephemeral=True)

    alert = app_commands.Group(
        name="alert",
        description="Manage server status alerts.",
    )
    display = app_commands.Group(
        name="display",
        description="Manage server status displays.",
    )
    query = app_commands.Group(
        name="query",
        description="Manage server status query.",
    )

    @tasks.loop(seconds=60)
    async def query_loop(self) -> None:
        guild_ids = [guild.id for guild in self.bot.guilds]
        async with connect() as conn:
            statuses = await fetch_statuses(conn, enabled=True, guild_ids=guild_ids)

    @query_loop.before_loop
    async def query_before_loop(self) -> None:
        delay = 60 - time.time() % 60
        log.info("Waiting %.2fs before starting query loop...", delay)
        await asyncio.sleep(delay)
