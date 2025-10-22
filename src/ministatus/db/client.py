from typing import Any

from ministatus.db.connection import Connection


class DatabaseClient:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    async def get_setting(self, name: str, default: Any = None) -> Any:
        row = await self.conn.fetchrow(
            "SELECT value FROM setting WHERE name = $1",
            name,
        )
        if row is None:
            return default
        return row[0]

    async def set_setting(self, name: str, value: Any) -> None:
        await self.conn.execute(
            "INSERT INTO setting (name, value) VALUES ($1, $2) "
            "ON CONFLICT (name) DO UPDATE SET value = excluded.value",
            name,
            value,
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
            "INSERT INTO discord_channel (message_id, channel_id) VALUES ($1, $2) "
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
