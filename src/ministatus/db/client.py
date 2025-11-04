from __future__ import annotations

import datetime
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
    StatusHistory,
    StatusHistoryPlayer,
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
            "(guild_id, label, title, address, thumbnail, enabled_at, failed_at, game, map, mods, version) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) RETURNING *",
            status.guild_id,
            status.label,
            status.title,
            status.address,
            status.thumbnail,
            status.enabled_at,
            status.failed_at,
            status.game,
            status.map,
            status.mods,
            status.version,
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
            "(status_id, channel_id, enabled_at, failed_at, send_audit, send_downtime) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
            alert.status_id,
            alert.channel_id,
            alert.enabled_at,
            alert.failed_at,
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
            "(message_id, status_id, enabled_at, failed_at, accent_colour, graph_colour, graph_interval) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *",
            display.message_id,
            display.status_id,
            display.enabled_at,
            display.failed_at,
            display.accent_colour,
            display.graph_colour,
            display.graph_interval,
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
            "(status_id, host, game_port, query_port, type, priority, enabled_at, failed_at, extra) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *",
            query.status_id,
            query.host,
            query.game_port,
            query.query_port,
            query.type,
            query.priority,
            query.enabled_at,
            query.failed_at,
            query.extra,
        )
        assert row is not None
        return StatusQuery.model_validate(dict(row))

    async def get_status(self, *, status_id: int) -> Status | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM status WHERE status_id = $1",
            status_id,
        )
        if row is not None:
            return Status(
                status_id=row["status_id"],
                guild_id=row["guild_id"],
                label=row["label"],
                title=row["title"],
                address=row["address"],
                thumbnail=row["thumbnail"],
                enabled_at=row["enabled_at"],
                failed_at=row["failed_at"],
                game=row["game"],
                map=row["map"],
                mods=row["mods"],
                version=row["version"],
            )

    async def get_status_display(self, *, message_id: int) -> StatusDisplay | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM status_display WHERE message_id = $1",
            message_id,
        )
        if row is not None:
            return StatusDisplay(
                message_id=row["message_id"],
                status_id=row["status_id"],
                enabled_at=row["enabled_at"],
                failed_at=row["failed_at"],
                accent_colour=row["accent_colour"],
                graph_colour=row["graph_colour"],
                graph_interval=row["graph_interval"],
            )

    # Composite status queries

    async def get_bulk_statuses(
        self,
        *status_ids: int,
        only_enabled: bool = False,
        with_relationships: bool = False,
    ) -> list[Status]:
        if not status_ids:
            return []

        enabled_expr = self._get_only_enabled_condition(only_enabled)
        sid = ", ".join("?" * len(status_ids))
        statuses = await self.conn.fetch(
            f"SELECT * FROM status WHERE {enabled_expr} AND status_id IN ({sid})",
            *status_ids,
        )

        if with_relationships:
            status_alerts = await self.get_bulk_status_alerts(
                *status_ids, only_enabled=only_enabled
            )
            status_displays = await self.get_bulk_status_displays(
                *status_ids, only_enabled=only_enabled
            )
            status_queries = await self.get_bulk_status_queries(
                *status_ids, only_enabled=only_enabled
            )
        else:
            status_alerts = {}
            status_displays = {}
            status_queries = {}

        status_objs = []
        for row in statuses:
            status_id = row["status_id"]
            status = Status(
                status_id=status_id,
                guild_id=row["guild_id"],
                label=row["label"],
                title=row["title"],
                address=row["address"],
                thumbnail=row["thumbnail"],
                enabled_at=row["enabled_at"],
                failed_at=row["failed_at"],
                game=row["game"],
                map=row["map"],
                mods=row["mods"],
                version=row["version"],
                alerts=status_alerts[status_id],
                displays=status_displays[status_id],
                queries=status_queries[status_id],
            )
            status_objs.append(status)

        return status_objs

    async def get_bulk_statuses_by_guilds(
        self,
        *guild_ids: int,
        only_enabled: bool = False,
        with_relationships: bool = False,
    ) -> list[Status]:
        if not guild_ids:
            return []

        enabled_expr = self._get_only_enabled_condition(only_enabled)
        gid = ", ".join("?" * len(guild_ids))
        rows = await self.conn.fetch(
            f"SELECT DISTINCT status_id FROM status WHERE {enabled_expr} "
            f"AND guild_id IN ({gid})",
            *guild_ids,
        )
        status_ids = [row["status_id"] for row in rows]

        return await self.get_bulk_statuses(
            *status_ids,
            only_enabled=only_enabled,
            with_relationships=with_relationships,
        )

    @staticmethod
    def _get_only_enabled_condition(only_enabled: bool) -> str:
        return "enabled_at IS NOT NULL" if only_enabled else "true"

    async def get_bulk_status_alerts(
        self,
        *status_ids: int,
        only_enabled: bool = False,
    ) -> dict[int, list[StatusAlert]]:
        status_alerts = {status_id: [] for status_id in status_ids}
        if not status_ids:
            return status_alerts

        enabled_expr = self._get_only_enabled_condition(only_enabled)
        sid = ", ".join("?" * len(status_ids))
        alerts = await self.conn.fetch(
            f"SELECT * FROM status_alert WHERE status_id IN ({sid}) "
            f"AND {enabled_expr} ORDER BY status_alert_id",
            *status_ids,
        )

        for row in alerts:
            alert = StatusAlert(
                status_alert_id=row["status_alert_id"],
                status_id=row["status_id"],
                channel_id=row["channel_id"],
                enabled_at=row["enabled_at"],
                failed_at=row["failed_at"],
                send_audit=row["send_audit"],
                send_downtime=row["send_downtime"],
            )
            status_alerts[row["status_id"]].append(alert)

        return status_alerts

    async def get_bulk_status_displays(
        self,
        *status_ids: int,
        only_enabled: bool = False,
    ) -> dict[int, list[StatusDisplay]]:
        status_displays = {status_id: [] for status_id in status_ids}
        if not status_ids:
            return status_displays

        enabled_expr = self._get_only_enabled_condition(only_enabled)
        sid = ", ".join("?" * len(status_ids))
        displays = await self.conn.fetch(
            f"SELECT * FROM status_display WHERE status_id IN ({sid}) "
            f"AND {enabled_expr} ORDER BY message_id",
            *status_ids,
        )

        for row in displays:
            display = StatusDisplay(
                message_id=row["message_id"],
                status_id=row["status_id"],
                enabled_at=row["enabled_at"],
                failed_at=row["failed_at"],
                accent_colour=row["accent_colour"],
                graph_colour=row["graph_colour"],
                graph_interval=row["graph_interval"],
            )
            status_displays[row["status_id"]].append(display)

        return status_displays

    async def get_bulk_status_queries(
        self,
        *status_ids: int,
        only_enabled: bool = False,
    ) -> dict[int, list[StatusQuery]]:
        status_queries = {status_id: [] for status_id in status_ids}
        if not status_ids:
            return status_queries

        enabled_expr = self._get_only_enabled_condition(only_enabled)
        sid = ", ".join("?" * len(status_ids))
        queries = await self.conn.fetch(
            f"SELECT * FROM status_query WHERE status_id IN ({sid}) "
            f"AND {enabled_expr} ORDER BY priority, status_query_id",
            *status_ids,
        )

        for row in queries:
            query = StatusQuery(
                status_query_id=row["status_query_id"],
                status_id=row["status_id"],
                host=row["host"],
                game_port=row["game_port"],
                query_port=row["query_port"],
                type=row["type"],
                priority=row["priority"],
                enabled_at=row["enabled_at"],
                failed_at=row["failed_at"],
                extra=row["extra"],
            )
            status_queries[row["status_id"]].append(query)

        return status_queries

    async def get_bulk_status_history(
        self,
        *status_ids: int,
        after: datetime.datetime,
        unknown: bool = True,
    ) -> dict[int, list[StatusHistory]]:
        history_models = {status_id: [] for status_id in status_ids}
        if not status_ids:
            return history_models

        sid = ", ".join("?" * len(status_ids))
        unknown_expr = "true" if unknown else "online OR down"
        history_rows = await self.conn.fetch(
            f"SELECT * FROM status_history WHERE status_id IN ({sid}) "
            f"AND created_at >= ? AND {unknown_expr} "
            f"ORDER BY status_id, created_at",
            *status_ids,
            after,
        )

        history_ids = {row["status_history_id"] for row in history_rows}
        history_players = await self.get_bulk_status_history_players(*history_ids)

        for row in history_rows:
            players = history_players[row["status_history_id"]]
            model = StatusHistory(
                status_history_id=row["status_history_id"],
                created_at=row["created_at"],
                status_id=row["status_id"],
                online=row["online"],
                max_players=row["max_players"],
                num_players=row["num_players"],
                down=row["down"],
                players=players,
            )
            history_models[model.status_id].append(model)

        return history_models

    async def get_bulk_status_history_players(
        self,
        *history_ids: int,
    ) -> dict[int, list[StatusHistoryPlayer]]:
        history_players = {history_id: [] for history_id in history_ids}
        if not history_ids:
            return history_players

        hid = ", ".join("?" * len(history_ids))
        players = await self.conn.fetch(
            f"SELECT * FROM status_history_player WHERE status_history_id IN ({hid}) "
            f"ORDER BY status_history_player_id",
            *history_ids,
        )

        for p in players:
            p = StatusHistoryPlayer(
                status_history_player_id=p["status_history_player_id"],
                status_history_id=p["status_history_id"],
                name=p["name"],
            )
            history_players[p.status_history_id].append(p)

        return history_players
