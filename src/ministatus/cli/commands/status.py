from __future__ import annotations

import datetime
import textwrap
import tomllib

import click

from ministatus.cli.commands.markers import mark_async, mark_db
from ministatus.db import Status, connect_client

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
    guild_id = -1         # Your guild ID

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
    status.enabled_at = enabled_at = datetime.datetime.now(datetime.timezone.utc)

    async with connect_client() as client:
        status = await client.create_status(status)

        for alert in status.alerts:
            alert.status_id = status.status_id
            alert.enabled_at = enabled_at
            await client.create_status_alert(alert)

        for display in status.displays:
            display.status_id = status.status_id
            display.enabled_at = enabled_at
            await client.create_status_display(display)

        for query in status.queries:
            query.status_id = status.status_id
            query.enabled_at = enabled_at
            await client.create_status_query(query)

    click.secho(f"Successfully created status #{status.status_id}!", fg="green")


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
