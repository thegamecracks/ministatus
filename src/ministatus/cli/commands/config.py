from contextlib import suppress
from typing import Any

import click

from ministatus.cli.commands.markers import mark_async, mark_db
from ministatus.db import DatabaseClient, Secret, SQLiteConnection, connect


@click.command()
@click.option("--unset", is_flag=True)
@click.argument("name", default="")
@click.argument("value", default=None)
@click.pass_context
@mark_async()
@mark_db()
async def config(
    ctx: click.Context,
    name: str,
    value: str | None,
    unset: bool,
) -> None:
    """Get or set a configuration setting."""
    async with connect() as conn:
        if name == "":
            await list_settings(conn)
        elif value is None and not unset:
            await get_setting(conn, name)
        elif value is None and unset:
            await delete_setting(conn, name)
        elif value is not None and not unset:
            parsed = parse_value(value)
            await set_setting(conn, name, parsed)
        elif value is not None and unset:
            raise click.BadOptionUsage(
                "--unset",
                "Cannot pass value and --unset at the same time",
            )


async def list_settings(conn: SQLiteConnection) -> None:
    client = DatabaseClient(conn)
    rows = await client.list_settings()
    if not rows:
        return click.echo("There are no settings defined 🙁")

    click.echo("Settings:")
    for name, value in rows:
        name = click.style(name, fg="yellow")
        value = click.style(value, fg="green")
        click.secho(f"    {name} = {value}")


async def get_setting(conn: SQLiteConnection, name: str) -> None:
    client = DatabaseClient(conn)
    sentinel = object()

    value = await client.get_setting(name, sentinel)
    if value is sentinel:
        return click.secho(f"{name!r} not found", fg="yellow")

    if isinstance(value, Secret):
        value = value.get_secret_value()

    click.secho(value, fg="green")


async def set_setting(conn: SQLiteConnection, name: str, value: Any) -> None:
    client = DatabaseClient(conn)
    await client.set_setting(name, value)


async def delete_setting(conn: SQLiteConnection, name: str) -> None:
    client = DatabaseClient(conn)
    found = await client.delete_setting(name)
    if not found:
        return click.secho(f"{name!r} not found", fg="yellow")


def parse_value(value: str) -> float | int | str | None:
    if value.lower() == "null":
        return None

    with suppress(ValueError):
        return int(value)

    with suppress(ValueError):
        return float(value)

    return value
