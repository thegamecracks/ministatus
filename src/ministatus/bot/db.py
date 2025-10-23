from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from ministatus.db import DatabaseClient, connect_client

if TYPE_CHECKING:
    import discord

    from ministatus.bot.bot import Bot


@asynccontextmanager
async def connect_discord_database_client(
    bot: Bot,
    *,
    transaction: bool = True,
) -> AsyncIterator[DiscordDatabaseClient]:
    async with connect_client(transaction=transaction) as client:
        yield DiscordDatabaseClient(bot, client)


class DiscordDatabaseClient:
    def __init__(self, bot: Bot, client: DatabaseClient) -> None:
        self.bot = bot
        self.client = client

    async def add_user(self, user: discord.User | discord.Member) -> None:
        await self.client.add_discord_user(user_id=user.id)

    async def add_user_or_member(self, user: discord.User | discord.Member) -> None:
        if isinstance(user, discord.Member):
            await self.add_member(user)
        else:
            await self.add_user(user)

    async def add_guild(self, guild: discord.Guild) -> None:
        await self.client.add_discord_guild(guild_id=guild.id)

    async def add_channel(self, channel: discord.abc.MessageableChannel) -> None:
        guild = channel.guild
        if guild is not None:
            await self.add_guild(guild)

        await self.client.add_discord_channel(
            channel_id=channel.id,
            guild_id=guild.id if guild is not None else None,
        )

    async def add_message(self, message: discord.Message) -> None:
        await self.add_channel(message.channel)
        await self.client.add_discord_message(
            message_id=message.id,
            channel_id=message.channel.id,
        )

    async def add_member(self, member: discord.Member) -> None:
        await self.add_user(member)
        await self.add_guild(member.guild)
        await self.client.add_discord_member(
            guild_id=member.guild.id,
            user_id=member.id,
        )

    async def get_channel(self, *, channel_id: int):
        channel = await self.client.get_discord_channel(channel_id=channel_id)
        if channel is None:
            return

        guild_id = channel.guild_id
        guild = self.bot.get_guild(guild_id) if guild_id is not None else None
        channel = (
            guild.get_channel_or_thread(channel_id)
            if guild is not None
            else self.bot.get_channel(channel_id)
        )

        if channel is None:
            channel = self.bot.get_partial_messageable(channel_id, guild_id=guild_id)

        return channel

    async def get_message(self, *, message_id: int) -> discord.PartialMessage | None:
        message = await self.client.get_discord_message(message_id=message_id)
        if message is None:
            return

        channel_id = message.channel_id
        channel = await self.get_channel(channel_id=channel_id)
        assert channel is not None

        # NOTE: Not all channel types support get_partial_message()
        try:
            return channel.get_partial_message(message_id)  # type: ignore
        except AttributeError:
            return
