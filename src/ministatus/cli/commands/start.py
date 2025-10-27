import logging

import click

from ministatus.cli.commands import read_token
from ministatus.cli.commands.markers import mark_async, mark_db

log = logging.getLogger(__name__)


@click.command()
@click.option("--sync", is_flag=True, help="Synchronize application commands.")
@mark_async()
@mark_db()
async def start(sync: bool) -> None:
    """Start the Discord bot in the current process."""
    token = await read_token()

    from ministatus.bot.bot import Bot

    bot = Bot()
    await bot.start(token.get_secret_value(), sync=sync)
