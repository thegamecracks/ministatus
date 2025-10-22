import re

import click

from ministatus.cli.commands.asyncio import mark_async
from ministatus.db import Secret


@click.command()
@mark_async()
async def start() -> None:
    """Start the Discord bot in the current process."""
    token = await read_token()

    from ministatus.bot.bot import Bot

    # TODO: invalidate token on login failure?
    bot = Bot()
    await bot.start(token.get_secret_value())


async def read_token() -> Secret[str]:
    from ministatus.db import connect_client

    async with connect_client() as client:
        token = await client.get_setting("token")

    if token is not None:
        return parse_token(token)

    click.secho("No Discord bot token found in config.", fg="yellow")
    click.echo("Would you like to enter your token now?")
    click.echo("You can change your token at any time using the 'config' command.")
    click.confirm("", abort=True)
    click.echo("Your Discord bot token should look something like this:")
    click.secho(
        "    MTI0NjgyNjg0MTIzMTMyNzI3NQ.GTIAZm.x2fbSNuYJgpAocvMM53ROlMC23NixWt-0NOjMc",
        fg="green",
    )
    token = click.prompt("Token", hide_input=True, type=parse_token)

    async with connect_client() as client:
        await client.set_setting("token", token)

    return token


def parse_token(token: str | Secret[str]) -> Secret[str]:
    if isinstance(token, Secret):
        token = token.get_secret_value()  # Was read from database

    token = token.strip()
    if not re.fullmatch(r"\w+\.\w+\.\S+", token):
        raise ValueError("Invalid token format")
    return Secret(token)
