from __future__ import annotations

import collections
import datetime
from dataclasses import dataclass
from typing import Any

from ministatus.db.connection import SQLiteConnection


@dataclass
class Status:
    status_id: int
    user_id: int
    label: str

    title: str | None
    address: str | None
    thumbnail: bytes | None
    enabled_at: datetime.datetime | None

    alert: StatusAlert | None
    displays: list[StatusDisplay]
    queries: list[StatusQuery]


@dataclass
class StatusAlert:
    status_id: int
    channel_id: int
    enabled_at: datetime.datetime | None


@dataclass
class StatusDisplay:
    message_id: int
    status_id: int

    enabled_at: datetime.datetime | None
    accent_colour: int
    graph_colour: int


@dataclass
class StatusQuery:
    status_id: int
    host: str
    port: int
    type: str
    priority: int

    enabled_at: datetime.datetime | None
    extra: Any
    failed_at: datetime.datetime | None


async def fetch_active_statuses(conn: SQLiteConnection) -> list[Status]:
    statuses = await conn.fetch("SELECT * FROM status WHERE enabled_at IS NOT NULL")
    if not statuses:
        return []

    status_ids = {row["status_id"] for row in statuses}
    sid = ", ".join("?" * len(status_ids))

    alerts = await conn.fetch(
        f"SELECT * FROM status_alert WHERE status_id IN ({sid}) "
        "AND enabled_at IS NOT NULL",
        *status_ids,
    )
    status_alerts = {
        row["status_id"]: StatusAlert(
            status_id=row["status_id"],
            channel_id=row["channel_id"],
            enabled_at=row["enabled_at"],
        )
        for row in alerts
    }

    displays = await conn.fetch(
        f"SELECT * FROM status_display WHERE status_id IN ({sid}) "
        "AND enabled_at IS NOT NULL",
        *status_ids,
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

    return [
        Status(
            status_id=row["status_id"],
            user_id=row["user_id"],
            label=row["label"],
            title=row["title"],
            address=row["address"],
            thumbnail=row["thumbnail"],
            enabled_at=row["enabled_at"],
            alert=status_alerts.get(row["status_id"]),
            displays=status_displays[row["status_id"]],
            queries=status_queries[row["status_id"]],
        )
        for row in statuses
    ]
