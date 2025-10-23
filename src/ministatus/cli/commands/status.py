from __future__ import annotations

import datetime
import textwrap
import tomllib

import click

from ministatus.cli.commands.markers import mark_async, mark_db
from ministatus.db import Status, connect

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

    [[status.alerts]]
    channel_id = -1 # Channel ID to send alerts to

    [[status.displays]]
    message_id = -1          # The message ID of a placeholder sent by the bot
    accent_colour = 0xFFFFFF # The accent colour to show
    graph_colour = 0xFFFFFF  # The graph colour to show

    [[status.queries]]
    host = "127.0.0.1"  # Your server's hostname or IP address
    port = -1           # Your server's query port (or 0 for SRV lookup)
    type = "source"     # The query protocol to use ({", ".join(TYPES_ALLOWED)})
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
    status = fill_status_form()
    enabled_at = datetime.datetime.now(datetime.timezone.utc)

    async with connect() as conn:
        # TODO: add status methods to DatabaseClient
        status_id = await conn.fetchval(
            "INSERT INTO status (user_id, label, enabled_at) "
            "VALUES ($1, $2, $3) RETURNING status_id",
            status.user_id,
            status.label,
            enabled_at,
        )

        for alert in status.alerts:
            channel_id = alert.channel_id
            await conn.execute(
                "INSERT INTO status_alert (status_id, channel_id, enabled_at) "
                "VALUES ($1, $2, $3)",
                status_id,
                channel_id,
                enabled_at,
            )

        for display in status.displays:
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

        for query in status.queries:
            await conn.execute(
                "INSERT INTO status_query "
                "(status_id, host, port, type, priority, enabled_at, extra) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                status_id,
                query.host,
                query.port,
                query.type,
                query.priority,
                enabled_at,
                query.extra,
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

            data["status"]["status_id"] = 0
            for alert in data["status"]["alerts"]:
                alert["status_id"] = 0
            for display in data["status"]["displays"]:
                display["status_id"] = 0
            for query in data["status"]["queries"]:
                query["status_id"] = 0

            return Status.model_validate(data["status"])
        except (KeyError, ValueError) as e:
            click.secho("Failed to parse your input:", fg="red")
            click.secho(textwrap.indent(str(e), "    "), fg="red")
            click.confirm("Would you like to try again?", abort=True)
            continue
