from __future__ import annotations

import collections
import datetime
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Collection

if TYPE_CHECKING:
    from ministatus.db.connection import SQLiteConnection


GET_STATUS_ALERTS = textwrap.dedent(
    """
    SELECT * FROM status_alert
    WHERE status_id IN ({sid})
    AND enabled_at IS NOT NULL
    AND channel_id IN (
        SELECT channel_id FROM discord_channel
        WHERE guild_id IN ({gid})
    )
    """
).strip()

GET_STATUS_DISPLAYS = textwrap.dedent(
    """
    SELECT * FROM status_display
    WHERE status_id IN ({sid})
    AND enabled_at IS NOT NULL
    AND message_id IN (
        SELECT message_id FROM discord_message
        WHERE channel_id IN (
            SELECT channel_id FROM discord_channel
            WHERE guild_id IN ({gid})
        )
    )
    """
).strip()


@dataclass(kw_only=True)
class Status:
    status_id: int
    user_id: int
    label: str

    title: str | None
    address: str | None
    thumbnail: bytes | None
    enabled_at: datetime.datetime | None

    alerts: list[StatusAlert]
    displays: list[StatusDisplay]
    queries: list[StatusQuery]


@dataclass(kw_only=True)
class StatusAlert:
    status_id: int
    channel_id: int
    enabled_at: datetime.datetime | None


@dataclass(kw_only=True)
class StatusDisplay:
    message_id: int
    status_id: int

    enabled_at: datetime.datetime | None
    accent_colour: int
    graph_colour: int


@dataclass(kw_only=True)
class StatusQuery:
    status_id: int
    host: str
    port: int
    type: str
    priority: int

    enabled_at: datetime.datetime | None
    extra: Any
    failed_at: datetime.datetime | None


async def fetch_active_statuses(
    conn: SQLiteConnection,
    *,
    guild_ids: Collection[int],
) -> list[Status]:
    if not guild_ids:
        return []

    statuses = await conn.fetch("SELECT * FROM status WHERE enabled_at IS NOT NULL")
    if not statuses:
        return []

    status_ids = {row["status_id"] for row in statuses}
    status_alerts = await fetch_status_alerts(
        conn,
        status_ids=status_ids,
        guild_ids=guild_ids,
    )
    status_displays = await fetch_status_displays(
        conn,
        status_ids=status_ids,
        guild_ids=guild_ids,
    )
    status_queries = await fetch_status_queries(conn, status_ids=status_ids)

    statuses = []
    for row in statuses:
        alerts = status_alerts[row["status_id"]]
        displays = status_displays[row["status_id"]]
        queries = status_queries[row["status_id"]]
        if not displays or not queries:
            continue  # Would be nice to filter this in SQL

        status = Status(
            status_id=row["status_id"],
            user_id=row["user_id"],
            label=row["label"],
            title=row["title"],
            address=row["address"],
            thumbnail=row["thumbnail"],
            enabled_at=row["enabled_at"],
            alerts=alerts,
            displays=displays,
            queries=queries,
        )
        statuses.append(status)

    return statuses


async def fetch_status_alerts(
    conn: SQLiteConnection,
    *,
    status_ids: Collection[int],
    guild_ids: Collection[int],
) -> dict[int, list[StatusAlert]]:
    assert len(status_ids) > 0
    assert len(guild_ids) > 0

    sid = ", ".join("?" * len(status_ids))
    gid = ", ".join("?" * len(guild_ids))
    alerts = await conn.fetch(
        GET_STATUS_ALERTS.format(sid=sid, gid=gid),
        *status_ids,
        *guild_ids,
    )

    status_alerts = collections.defaultdict(list)
    for row in alerts:
        alert = StatusAlert(
            status_id=row["status_id"],
            channel_id=row["channel_id"],
            enabled_at=row["enabled_at"],
        )
        status_alerts[row["status_id"]].append(alert)

    return status_alerts


async def fetch_status_displays(
    conn: SQLiteConnection,
    *,
    status_ids: Collection[int],
    guild_ids: Collection[int],
) -> dict[int, list[StatusDisplay]]:
    assert len(status_ids) > 0
    assert len(guild_ids) > 0

    sid = ", ".join("?" * len(status_ids))
    gid = ", ".join("?" * len(guild_ids))
    displays = await conn.fetch(
        GET_STATUS_DISPLAYS.format(sid=sid, gid=gid),
        *status_ids,
        *guild_ids,
    )

    status_displays = collections.defaultdict(list)
    for row in displays:
        display = StatusDisplay(
            message_id=row["message_id"],
            status_id=row["status_id"],
            enabled_at=row["enabled_at"],
            accent_colour=row["accent_colour"],
            graph_colour=row["graph_colour"],
        )
        status_displays[row["status_id"]].append(display)

    return status_displays


async def fetch_status_queries(
    conn: SQLiteConnection,
    *,
    status_ids: Collection[int],
) -> dict[int, list[StatusQuery]]:
    assert len(status_ids) > 0

    sid = ", ".join("?" * len(status_ids))
    queries = await conn.fetch(
        f"SELECT * FROM status_query WHERE status_id IN ({sid}) "
        "AND enabled_at IS NOT NULL ORDER BY priority",
        *status_ids,
    )

    status_queries = collections.defaultdict(list)
    for row in queries:
        query = StatusQuery(
            status_id=row["status_id"],
            host=row["host"],
            port=row["port"],
            type=row["type"],
            priority=row["priority"],
            enabled_at=row["enabled_at"],
            extra=row["extra"],
            failed_at=row["failed_at"],
        )
        status_queries[row["status_id"]].append(query)

    return status_queries
