import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ministatus.bot.bot import Bot
from ministatus.bot.db import DiscordDatabaseClient, fetch_active_statuses
from ministatus.db import connect, connect_client

from .views import PlaceholderView

log = logging.getLogger(__name__)


class Status(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.query.start()

    @app_commands.command(name="create-display")
    @app_commands.allowed_contexts(guilds=True)
    @app_commands.allowed_installs(guilds=True)
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.channel_id)
    @app_commands.default_permissions(manage_guild=True)
    async def create_status_display(
        self,
        interaction: discord.Interaction[Bot],
    ) -> None:
        """Create a placeholder display to later be linked to a status."""
        assert interaction.channel is not None
        assert interaction.guild_id is not None
        assert not isinstance(
            interaction.channel, (discord.CategoryChannel, discord.ForumChannel)
        )

        view = PlaceholderView(interaction.user)
        message = await interaction.channel.send(view=view)

        async with connect_client() as client:
            discord_client = DiscordDatabaseClient(client)
            await discord_client.add_message(message)

        await interaction.response.send_message(
            f"**Message ID**: {message.id}\n"
            f"**Channel ID**: {interaction.channel.id}",
            ephemeral=True,
        )

    @tasks.loop(seconds=60)
    async def query(self) -> None:
        async with connect() as conn:
            statuses = await fetch_active_statuses(conn)

    @query.before_loop
    async def query_before_loop(self) -> None:
        delay = 60 - time.time() % 60
        log.info("Waiting %.2fs before starting query loop...", delay)
        await asyncio.sleep(delay)
