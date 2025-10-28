import datetime
import logging
import random
import re
import sys

import click

from ministatus.appdirs import DB_PATH
from ministatus.bot.dt import past
from ministatus.cli.commands.markers import mark_async, mark_db
from ministatus.db import connect, connect_sync


def parse_interval(s: str) -> datetime.timedelta:
    m = re.match(r"(\d+)([smhd])", s.strip().lower())
    if m is None:
        raise ValueError("Interval must be in the format N[smhd]")

    n, t = int(m[1]), m[2]
    if t == "s":
        return datetime.timedelta(seconds=n)
    elif t == "m":
        return datetime.timedelta(minutes=n)
    elif t == "h":
        return datetime.timedelta(hours=n)
    elif t == "d":
        return datetime.timedelta(days=n)

    raise RuntimeError(f"Unhandled type {t}")


@click.group(hidden=True)
def debug() -> None:
    """Internal debugging utilities."""


@debug.command()
def levels() -> None:
    """Trigger info and debug logs to test logging verbosity."""
    logging.getLogger(__name__).info("Test 1")
    logging.getLogger(__name__).debug("Test 2")
    logging.getLogger().info("Test 3")
    logging.getLogger().debug("Test 4")


@debug.command()
@click.option(
    "-f",
    "--frequency",
    default="1h",
    help="The interval between datapoints",
    type=parse_interval,
)
@click.option(
    "-p",
    "--period",
    default="1d",
    help="The period of time to generate",
    type=parse_interval,
)
@click.option("-m", "--max-players", default=40, help="The max number of players")
@click.argument("status_id", type=int)
@mark_async()
@mark_db()
async def fake_history(
    frequency: datetime.timedelta,
    period: datetime.timedelta,
    max_players: int,
    status_id: int,
) -> None:
    """Generate fake history for a given status."""
    names = ["foo", "bar", "baz"] * (max_players // 3 + 1)

    start = past(period)
    start = start.replace(second=0, microsecond=0)
    n = int(period.total_seconds() / frequency.total_seconds())

    data = [
        (start + frequency * i, names[: random.randrange(len(names) + 1)])
        for i in range(1, n + 1)
    ]

    print(f"Writing {n} datapoints...")
    async with connect() as conn:
        for created_at, players in data:
            status_history_id = await conn.fetchval(
                "INSERT INTO status_history "
                "(created_at, status_id, online, max_players, num_players) "
                "VALUES ($1, $2, $3, $4, $5) RETURNING status_history_id",
                created_at,
                status_id,
                True,
                max_players,
                len(players),
            )

            await conn.executemany(
                "INSERT INTO status_history_player (status_history_id, name) "
                "VALUES ($1, $2)",
                [(status_history_id, name) for name in players],
            )


@debug.command()
def imports() -> None:
    """Print all third-party modules imported at startup."""
    names = sorted(
        name
        for name in sys.modules
        if name.partition(".")[0] not in sys.stdlib_module_names
        and name not in ("__main__", "_virtualenv")
    )

    packages: dict[str, list[str]] = {}
    for name in names:
        package, _, submodule = name.partition(".")
        packages.setdefault(package, [])
        if submodule:
            packages[package].append(submodule)

    for package, submodules in packages.items():
        click.secho(package, fg="green")
        for mod in submodules:
            click.secho(f"  .{mod}", fg="yellow")


@debug.command()
@click.confirmation_option(
    prompt=click.style(
        "DANGER!! Are you sure you want to wipe the database?",
        fg="red",
    ),
)
def wipe() -> None:
    """Delete the current database."""
    with connect_sync(transaction=False) as conn:
        conn.execute("PRAGMA locking_mode = EXCLUSIVE")
        conn.execute("PRAGMA journal_mode = DELETE")
    DB_PATH.unlink()
