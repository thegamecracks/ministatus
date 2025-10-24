import logging

import click

from ministatus.cli.commands import read_token
from ministatus.cli.commands.markers import mark_async, mark_db

log = logging.getLogger(__name__)


@click.command()
@mark_async()
@mark_db()
async def start() -> None:
    """Start the Discord bot in the current process."""
    token = await read_token()

    from ministatus.bot.bot import Bot

    # TODO: invalidate token on login failure?
    bot = Bot()
    await bot.start(token.get_secret_value())
