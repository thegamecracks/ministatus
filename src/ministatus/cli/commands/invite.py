import click

from ministatus.cli.commands import read_token
from ministatus.cli.commands.markers import mark_async, mark_db
from ministatus.db import connect_client


@click.command()
@mark_async()
@mark_db()
async def invite() -> None:
    """Print the bot's invite link."""

    async with connect_client() as client:
        app_id = await client.get_setting("appid")

    from ministatus.bot.bot import Bot

    bot = Bot()
    if app_id is not None:
        return click.secho(bot.get_standard_invite(app_id), fg="cyan")

    click.secho(
        "Logging into your bot is required to generate the invite link.",
        err=True,
        fg="yellow",
    )
    click.confirm(
        click.style("Would you like to log in?", fg="yellow"),
        abort=True,
        err=True,
    )
    token = await read_token()
    await bot.login(token.get_secret_value())
    click.secho(bot.get_standard_invite(app_id), fg="cyan")
