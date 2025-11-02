from __future__ import annotations

from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    AsyncIterator,
    Literal,
    Protocol,
    cast,
    runtime_checkable,
)

from ministatus.db import DatabaseClient, StatusAlert, TransactionMode, connect_client

if TYPE_CHECKING:
    import discord

    from ministatus.bot.bot import Bot


@asynccontextmanager
async def connect_discord_database_client(
    bot: Bot,
    *,
    transaction: TransactionMode = True,
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
        import discord

        if isinstance(user, discord.Member):
            await self.add_member(user)
        else:
            await self.add_user(user)

    async def add_guild(self, guild: discord.Guild) -> None:
        await self.client.add_discord_guild(guild_id=guild.id)

    async def add_channel(self, channel: _ChannelLike) -> None:
        if isinstance(channel, _ChannelWithGuild):
            guild_id = channel.guild and channel.guild.id
        elif isinstance(channel, _ChannelWithGuildID):
            guild_id = channel.guild_id
        else:
            guild_id = None

        if guild_id is not None:
            await self.client.add_discord_guild(guild_id=guild_id)
        await self.client.add_discord_channel(channel_id=channel.id, guild_id=guild_id)

    async def add_message(self, message: discord.Message) -> None:
        await self.add_channel(message.channel)
        await self.add_user_or_member(message.author)
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
        if channel is not None:
            return self._resolve_channel(
                channel_id=channel.channel_id,
                guild_id=channel.guild_id,
            )

    async def get_message(self, *, message_id: int) -> discord.PartialMessage | None:
        row = await self.client.conn.fetchrow(
            "SELECT m.message_id, m.channel_id, c.guild_id FROM discord_message m "
            "JOIN discord_channel c USING (channel_id) "
            "WHERE message_id = $1",
            message_id,
        )
        if row is None:
            return

        message_id, channel_id, guild_id = row
        channel = self._resolve_channel(channel_id=channel_id, guild_id=guild_id)

        # NOTE: Not all channel types support get_partial_message()
        try:
            return channel.get_partial_message(message_id)  # type: ignore
        except AttributeError:
            return

    async def get_bulk_status_alert_channels(
        self,
        status_id: int,
        *,
        only_enabled: bool,
        type: Literal["audit", "downtime"] | None,
    ) -> list[tuple[StatusAlert, discord.abc.MessageableChannel]]:
        alerts = await self.client.get_bulk_status_alerts(
            status_id,
            only_enabled=only_enabled,
        )
        alerts = alerts[status_id]
        alerts = [  # FIXME: should filter this in SQL
            a
            for a in alerts
            if type is None
            or type == "audit"
            and a.send_audit
            or type == "downtime"
            and a.send_downtime
        ]

        alert_ids = [a.channel_id for a in alerts]
        aid = ", ".join("?" * len(alert_ids))
        channels = await self.client.conn.fetch(
            f"SELECT channel_id, guild_id FROM discord_channel "
            f"WHERE channel_id IN ({aid})",
            *alert_ids,
        )
        channels = {
            c["channel_id"]: self._resolve_channel(
                channel_id=c["channel_id"],
                guild_id=c["guild_id"],
            )
            for c in channels
        }
        channels = cast("dict[int, discord.abc.MessageableChannel]", channels)

        return [(alert, channels[alert.channel_id]) for alert in alerts]

    def _resolve_channel(self, *, channel_id: int, guild_id: int | None):
        guild = self.bot.get_guild(guild_id) if guild_id is not None else None
        channel = (
            guild.get_channel_or_thread(channel_id)
            if guild is not None
            else self.bot.get_channel(channel_id)
        )

        if channel is None:
            channel = self.bot.get_partial_messageable(channel_id, guild_id=guild_id)

        return channel


@runtime_checkable
class _Channel(Protocol):
    id: int


@runtime_checkable
class _ChannelWithGuild(_Channel, Protocol):
    id: int
    guild: discord.Guild | None


@runtime_checkable
class _ChannelWithGuildID(_Channel, Protocol):
    id: int
    guild_id: int | None


_ChannelLike = _ChannelWithGuild | _ChannelWithGuildID | _Channel
