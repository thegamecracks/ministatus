from __future__ import annotations

import collections
import textwrap
from typing import TYPE_CHECKING, Collection

from ministatus.db.models import (
    Status,
    StatusAlert,
    StatusDisplay,
    StatusHistory,
    StatusHistoryPlayer,
    StatusQuery,
)

if TYPE_CHECKING:
    from ministatus.db.connection import SQLiteConnection


GET_STATUS_ALERTS = textwrap.dedent(
    """
    SELECT * FROM status_alert
    WHERE status_id IN ({sid})
    AND {enabled}
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
    AND {enabled}
    AND message_id IN (
        SELECT message_id FROM discord_message
        WHERE channel_id IN (
            SELECT channel_id FROM discord_channel
            WHERE guild_id IN ({gid})
        )
    )
    """
).strip()


async def fetch_statuses(
    conn: SQLiteConnection,
    *,
    guild_ids: Collection[int],
    enabled: bool | None = None,
    with_relationships: bool = False,
) -> list[Status]:
    if not guild_ids:
        return []

    enabled_expr = get_enabled_condition(enabled)
    gid = ", ".join("?" * len(guild_ids))
    statuses = await conn.fetch(
        f"SELECT * FROM status WHERE {enabled_expr} AND guild_id IN ({gid})",
        *guild_ids,
    )
    if not statuses:
        return []

    status_ids = {row["status_id"] for row in statuses}
    status_alerts = (
        await fetch_status_alerts(
            conn,
            enabled=enabled or None,  # don't pass enabled=False down
            status_ids=status_ids,
            guild_ids=guild_ids,
        )
        if with_relationships
        else {}
    )
    status_displays = (
        await fetch_status_displays(
            conn,
            enabled=enabled or None,
            status_ids=status_ids,
            guild_ids=guild_ids,
        )
        if with_relationships
        else {}
    )
    status_queries = (
        await fetch_status_queries(
            conn,
            enabled=enabled or None,
            status_ids=status_ids,
        )
        if with_relationships
        else {}
    )

    status_objs = []
    for row in statuses:
        status_id = row["status_id"]
        alerts = status_alerts.get(status_id, [])
        displays = status_displays.get(status_id, [])
        queries = status_queries.get(status_id, [])
        if enabled and (not displays or not queries):
            continue  # Would be nice to filter this in SQL

        status = Status(
            status_id=status_id,
            guild_id=row["guild_id"],
            label=row["label"],
            title=row["title"],
            address=row["address"],
            thumbnail=row["thumbnail"],
            enabled_at=row["enabled_at"],
            alerts=alerts,
            displays=displays,
            queries=queries,
        )
        status_objs.append(status)

    return status_objs


def get_enabled_condition(enabled: bool | None) -> str:
    if enabled:
        return "enabled_at IS NOT NULL"
    elif enabled is not None:
        return "enabled_at IS NULL"
    else:
        return "true"


async def fetch_status_alerts(
    conn: SQLiteConnection,
    *,
    enabled: bool | None = None,
    status_ids: Collection[int],
    guild_ids: Collection[int],
) -> dict[int, list[StatusAlert]]:
    assert len(status_ids) > 0
    assert len(guild_ids) > 0

    alerts = await conn.fetch(
        GET_STATUS_ALERTS.format(
            enabled=get_enabled_condition(enabled),
            sid=", ".join("?" * len(status_ids)),
            gid=", ".join("?" * len(guild_ids)),
        ),
        *status_ids,
        *guild_ids,
    )

    status_alerts = collections.defaultdict(list)
    for row in alerts:
        alert = StatusAlert(
            status_id=row["status_id"],
            channel_id=row["channel_id"],
            enabled_at=row["enabled_at"],
            send_audit=row["send_audit"],
            send_downtime=row["send_downtime"],
        )
        status_alerts[row["status_id"]].append(alert)

    return status_alerts


async def fetch_status_displays(
    conn: SQLiteConnection,
    *,
    enabled: bool | None = None,
    status_ids: Collection[int],
    guild_ids: Collection[int],
) -> dict[int, list[StatusDisplay]]:
    assert len(status_ids) > 0
    assert len(guild_ids) > 0

    displays = await conn.fetch(
        GET_STATUS_DISPLAYS.format(
            enabled=get_enabled_condition(enabled),
            sid=", ".join("?" * len(status_ids)),
            gid=", ".join("?" * len(guild_ids)),
        ),
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
    enabled: bool | None = None,
    status_ids: Collection[int],
) -> dict[int, list[StatusQuery]]:
    assert len(status_ids) > 0

    enabled_expr = get_enabled_condition(enabled)
    sid = ", ".join("?" * len(status_ids))
    queries = await conn.fetch(
        f"SELECT * FROM status_query WHERE status_id IN ({sid}) "
        f"AND {enabled_expr} ORDER BY priority",
        *status_ids,
    )

    status_queries = collections.defaultdict(list)
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
            extra=row["extra"],
            failed_at=row["failed_at"],
        )
        status_queries[row["status_id"]].append(query)

    return status_queries


async def fetch_status_by_id(
    conn: SQLiteConnection,
    *,
    status_id: int,
) -> Status | None:
    row = await conn.fetchrow("SELECT * FROM status WHERE status_id = $1", status_id)
    if row is None:
        return

    return Status(
        status_id=row["status_id"],
        guild_id=row["guild_id"],
        label=row["label"],
        title=row["title"],
        address=row["address"],
        thumbnail=row["thumbnail"],
        enabled_at=row["enabled_at"],
    )


async def fetch_status_display_by_id(
    conn: SQLiteConnection,
    *,
    message_id: int,
) -> StatusDisplay | None:
    row = await conn.fetchrow(
        "SELECT * FROM status_display WHERE message_id = $1",
        message_id,
    )
    if row is None:
        return

    return StatusDisplay(
        message_id=row["message_id"],
        status_id=row["status_id"],
        enabled_at=row["enabled_at"],
        accent_colour=row["accent_colour"],
        graph_colour=row["graph_colour"],
    )


async def fetch_status_history(
    conn: SQLiteConnection,
    *,
    status_ids: Collection[int],
) -> dict[int, list[StatusHistory]]:
    if not status_ids:
        return {}

    sid = ", ".join("?" * len(status_ids))
    history_rows = await conn.fetch(
        f"SELECT * FROM status_history WHERE status_id IN ({sid}) "
        f"ORDER BY status_id, created_at",
        *status_ids,
    )

    history_ids = {row["status_history_id"] for row in history_rows}
    history_players = await fetch_status_history_players(conn, history_ids=history_ids)

    history_models = collections.defaultdict(list)
    for row in history_rows:
        players = history_players[row["status_history_id"]]
        model = StatusHistory(
            status_history_id=row["status_history_id"],
            created_at=row["created_at"],
            status_id=row["status_id"],
            online=row["online"],
            max_players=row["max_players"],
            players=players,
        )
        history_models[model.status_id].append(model)

    return history_models


async def fetch_status_history_players(
    conn: SQLiteConnection,
    *,
    history_ids: Collection[int],
) -> dict[int, list[StatusHistoryPlayer]]:
    if not history_ids:
        return {}

    hid = ", ".join("?" * len(history_ids))
    players = await conn.fetch(
        f"SELECT * FROM status_history_player WHERE status_history_id IN ({hid}) "
        f"ORDER BY status_history_player_id",
        *history_ids,
    )

    history_players = collections.defaultdict(list)
    for p in players:
        p = StatusHistoryPlayer(
            status_history_player_id=p["status_history_player_id"],
            status_history_id=p["status_history_id"],
            name=p["name"],
        )
        history_players[p.status_history_id].append(p)

    return history_players
