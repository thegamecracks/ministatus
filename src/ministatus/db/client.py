from __future__ import annotations

from typing import Any

from ministatus.db.connection import SQLiteConnection
from ministatus.db.models import (
    DiscordChannel,
    DiscordGuild,
    DiscordMember,
    DiscordMessage,
    DiscordUser,
    Status,
    StatusAlert,
    StatusDisplay,
    StatusQuery,
)
from ministatus.db.secret import Secret


class DatabaseClient:
    SECRET_SETTINGS = frozenset({"token"})
    """A set of setting names that will always be marked as secrets."""

    def __init__(self, conn: SQLiteConnection) -> None:
        self.conn = conn

    async def list_settings(self) -> list[tuple[str, Any]]:
        rows = await self.conn.fetch(
            "SELECT name, value, secret FROM setting ORDER BY name"
        )
        return [
            (name, Secret(value) if secret else value) for name, value, secret in rows
        ]

    async def get_setting(self, name: str, default: Any = None) -> Any:
        row = await self.conn.fetchrow(
            "SELECT value, secret FROM setting WHERE name = $1",
            name,
        )
        if row is None:
            return default
        elif row["secret"]:
            return Secret(row["value"])
        return row["value"]

    async def set_setting(
        self,
        name: str,
        value: Any,
        *,
        secret: bool = False,
    ) -> None:
        if name in self.SECRET_SETTINGS:
            secret = True

        # If a conflict occurs, don't overwrite the secret flag
        # so we avoid accidentally clearing it.
        await self.conn.execute(
            "INSERT INTO setting (name, value, secret) VALUES ($1, $2, $3) "
            "ON CONFLICT (name) DO UPDATE SET value = excluded.value",
            name,
            value,
            secret,
        )

    async def delete_setting(self, name: str) -> bool:
        ret = await self.conn.fetchval(
            "DELETE FROM setting WHERE name = $1 RETURNING 1",
            name,
        )
        return ret is not None

    async def add_discord_user(
        self,
        *,
        user_id: int,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO discord_user (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id,
        )

    async def add_discord_guild(
        self,
        *,
        guild_id: int,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO discord_guild (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
            guild_id,
        )

    async def add_discord_channel(
        self,
        *,
        channel_id: int,
        guild_id: int | None,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO discord_channel (channel_id, guild_id) VALUES ($1, $2) "
            "ON CONFLICT DO NOTHING",
            channel_id,
            guild_id,
        )

    async def add_discord_message(
        self,
        *,
        message_id: int,
        channel_id: int,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO discord_message (message_id, channel_id) VALUES ($1, $2) "
            "ON CONFLICT DO NOTHING",
            message_id,
            channel_id,
        )

    async def add_discord_member(
        self,
        *,
        guild_id: int,
        user_id: int,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO discord_member (guild_id, user_id) VALUES ($1, $2) "
            "ON CONFLICT DO NOTHING",
            guild_id,
            user_id,
        )

    async def get_discord_user(self, *, user_id: int) -> DiscordUser | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM discord_user WHERE user_id = $1",
            user_id,
        )
        if row is not None:
            return DiscordUser.model_validate(dict(row))

    async def get_discord_guild(self, *, guild_id: int) -> DiscordGuild | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM discord_guild WHERE guild_id = $1",
            guild_id,
        )
        if row is not None:
            return DiscordGuild.model_validate(dict(row))

    async def get_discord_channel(self, *, channel_id: int) -> DiscordChannel | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM discord_channel WHERE channel_id = $1",
            channel_id,
        )
        if row is not None:
            return DiscordChannel.model_validate(dict(row))

    async def get_discord_message(self, *, message_id: int) -> DiscordMessage | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM discord_message WHERE message_id = $1",
            message_id,
        )
        if row is not None:
            return DiscordMessage.model_validate(dict(row))

    async def get_discord_member(self, *, user_id: int) -> DiscordMember | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM discord_member WHERE user_id = $1",
            user_id,
        )
        if row is not None:
            return DiscordMember.model_validate(dict(row))

    async def create_status(self, status: Status) -> Status:
        if status.status_id > 0:
            raise ValueError("Cannot create status with explicit status_id")

        row = await self.conn.fetchrow(
            "INSERT INTO status "
            "(guild_id, label, title, address, thumbnail, enabled_at) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
            status.guild_id,
            status.label,
            status.title,
            status.address,
            status.thumbnail,
            status.enabled_at,
        )
        assert row is not None
        return Status.model_validate(dict(row))

    async def create_status_alert(self, alert: StatusAlert) -> StatusAlert:
        if alert.status_alert_id > 0:
            raise ValueError("Cannot create status alert with explicit status_alert_id")
        elif alert.status_id < 1:
            raise ValueError("Cannot create status alert without status_id")

        row = await self.conn.fetchrow(
            "INSERT INTO status_alert "
            "(status_id, channel_id, enabled_at, send_audit, send_downtime) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING *",
            alert.status_id,
            alert.channel_id,
            alert.enabled_at,
            alert.send_audit,
            alert.send_downtime,
        )
        assert row is not None
        return StatusAlert.model_validate(dict(row))

    async def create_status_display(self, display: StatusDisplay) -> StatusDisplay:
        if display.message_id < 1:
            raise ValueError("Cannot create status display without message_id")
        elif display.status_id < 1:
            raise ValueError("Cannot create status display without status_id")

        row = await self.conn.fetchrow(
            "INSERT INTO status_display "
            "(message_id, status_id, enabled_at, accent_colour, graph_colour) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING *",
            display.message_id,
            display.status_id,
            display.enabled_at,
            display.accent_colour,
            display.graph_colour,
        )
        assert row is not None
        return StatusDisplay.model_validate(dict(row))

    async def create_status_query(self, query: StatusQuery) -> StatusQuery:
        if query.status_query_id > 0:
            raise ValueError("Cannot create status query with explicit status_query_id")
        elif query.status_id < 1:
            raise ValueError("Cannot create status query without status_id")

        row = await self.conn.fetchrow(
            "INSERT INTO status_query "
            "(status_id, host, game_port, query_port, type, priority, enabled_at, extra, failed_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *",
            query.status_id,
            query.host,
            query.game_port,
            query.query_port,
            query.type,
            query.priority,
            query.enabled_at,
            query.extra,
            query.failed_at,
        )
        assert row is not None
        return StatusQuery.model_validate(dict(row))
