from __future__ import annotations

import datetime
import json
import textwrap
import tomllib
from dataclasses import dataclass
from typing import Any, ClassVar, Self

import click

from ministatus.cli.commands.markers import mark_async, mark_db
from ministatus.db import DatabaseClient, connect

TYPES_ALLOWED = (
    "arma3",
    "arma-reforger",
    "source",
    "project-zomboid",
)
STATUS_TEMPLATE = textwrap.dedent(
    f"""
    [status]
    label = "My server"  # A useful name for your server
    user_id = -1         # Your Discord user ID

    [status.alert]
    channel_id = -1 # Channel ID to send alerts to

    [[status.display]]
    channel_id = -1          # The channel ID of a placeholder sent by the bot
    message_id = -1          # The message ID of a placeholder sent by the bot
    accent_colour = 0xFFFFFF # The accent colour to show
    graph_colour = 0xFFFFFF  # The graph colour to show

    [[status.query]]
    host = "127.0.0.1"  # Your server's hostname or IP address
    port = -1           # Your server's query port (or 0 for SRV lookup)
    type = "source"     # The query protocol to use ({', '.join(TYPES_ALLOWED)})
    priority = 0        # The priority of this query protocol (0 is highest)
    extra = ""          # Extra data for the query protocol, like API keys
    """
).lstrip()


@click.group()
@mark_db()
def status() -> None:
    """Manage server statuses."""


@status.command()
@mark_async()
async def create() -> None:
    """Create a server status."""
    async with connect() as conn:
        client = DatabaseClient(conn)
        status = fill_status_form()
        enabled_at = datetime.datetime.now(datetime.timezone.utc)

        await client.add_discord_user(user_id=status.user_id)
        # TODO: add status methods to DatabaseClient
        status_id = await conn.fetchval(
            "INSERT INTO status (user_id, label, enabled_at) "
            "VALUES ($1, $2, $3) RETURNING status_id",
            status.user_id,
            status.label,
            enabled_at,
        )

        if status.alert is not None:
            channel_id = status.alert.channel_id
            await client.add_discord_channel(channel_id=channel_id, guild_id=None)
            await conn.execute(
                "INSERT INTO status_alert (status_id, channel_id, enabled_at) "
                "VALUES ($1, $2, $3)",
                status_id,
                channel_id,
                enabled_at,
            )

        for display in status.displays:
            channel_id = display.channel_id
            await client.add_discord_channel(channel_id=channel_id, guild_id=None)
            await client.add_discord_message(
                message_id=display.message_id,
                channel_id=channel_id,
            )
            await conn.execute(
                "INSERT INTO status_display "
                "(message_id, status_id, enabled_at, accent_colour, graph_colour) "
                "VALUES ($1, $2, $3, $4, $5)",
                display.message_id,
                status_id,
                enabled_at,
                display.accent_colour,
                display.graph_colour,
            )

    click.secho(f"Successfully created status #{status_id}!", fg="green")


def fill_status_form() -> Status:
    content = STATUS_TEMPLATE
    while True:
        content = click.edit(content, extension=".toml")
        if content is None:
            raise click.Abort

        try:
            data = tomllib.loads(content)
            return Status.from_dict(data["status"])
        except (KeyError, ValueError) as e:
            click.secho("Failed to parse your input:", fg="red")
            click.secho(textwrap.indent(str(e), "    "), fg="red")
            click.confirm("Would you like to try again?", abort=True)
            continue


# FIXME: maybe use pydantic instead
@dataclass(kw_only=True)
class Status:
    user_id: int
    label: str
    alert: StatusAlert | None
    displays: list[StatusDisplay]
    queries: list[StatusQuery]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        user_id = int(d["user_id"])
        if user_id < 1:
            raise ValueError("user_id must be set")

        label = str(d["label"])
        if not label:
            raise ValueError("label must be set")

        alert = d.get("alert")
        if alert is not None:
            alert = StatusAlert.from_dict(alert)

        displays = [StatusDisplay.from_dict(x) for x in d.get("display", ())]
        queries = [StatusQuery.from_dict(x) for x in d.get("query", ())]

        return cls(
            user_id=user_id,
            label=label,
            alert=alert,
            displays=displays,
            queries=queries,
        )


@dataclass(kw_only=True)
class StatusAlert:
    channel_id: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        channel_id = int(d["channel_id"])
        if channel_id < 1:
            raise ValueError("channel_id must be set")

        return cls(channel_id=channel_id)


@dataclass(kw_only=True)
class StatusDisplay:
    channel_id: int
    message_id: int
    accent_colour: int
    graph_colour: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        channel_id = int(d["channel_id"])
        if channel_id < 1:
            raise ValueError("channel_id must be set")

        message_id = int(d["message_id"])
        if message_id < 1:
            raise ValueError("message_id must be set")

        accent_colour = int(d["accent_colour"])
        if not 0x000000 <= accent_colour <= 0xFFFFFF:
            raise ValueError("accent_colour must be a valid SRGB value")

        graph_colour = int(d["graph_colour"])
        if not 0x000000 <= graph_colour <= 0xFFFFFF:
            raise ValueError("graph_colour must be a valid SRGB value")

        return cls(
            channel_id=channel_id,
            message_id=message_id,
            accent_colour=accent_colour,
            graph_colour=graph_colour,
        )


@dataclass(kw_only=True)
class StatusQuery:
    host: str
    port: int
    type: str
    priority: int
    extra: object

    TYPES_ALLOWED: ClassVar[tuple[str, ...]] = TYPES_ALLOWED

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        host = str(d["host"])
        if not host:
            raise ValueError("host must be set")

        port = int(d["port"])
        if port < 0:
            raise ValueError("port must be set")

        type = str(d["type"])
        if type not in cls.TYPES_ALLOWED:
            allowed = ", ".join(cls.TYPES_ALLOWED)
            raise ValueError(f"type must be one of: {allowed}")

        priority = int(d["priority"])
        if priority < 0:
            raise ValueError("priority must be 0 or greater")

        extra = str(d["extra"])
        if extra:
            extra = json.loads(extra)

        return cls(
            host=host,
            port=port,
            type=type,
            priority=priority,
            extra=extra,
        )
