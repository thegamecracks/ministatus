import logging

import click

from ministatus import __version__, state
from ministatus.cli.commands import add_commands
from ministatus.db import Secret
from ministatus.logging import setup_logging

log = logging.getLogger(__name__)


CONTEXT_SETTINGS = dict(
    help_option_names=("-h", "--help"),
)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    "-p",
    "--password",
    default=None,
    envvar="MIST_PASSWORD",
    help="The password to unlock the database, if any",
    type=Secret,
)
@click.option("-v", "--verbose", count=True, help="Increase logging verbosity.")
@click.version_option(__version__, "-V", "--version")
def main(password: Secret[str] | None, verbose: int) -> None:
    """A Discord bot for managing game server status embeds."""
    setup_logging(verbose=verbose)
    if password is not None:
        set_database_password(password)


def set_database_password(password: Secret[str]) -> None:
    if not password.get_secret_value():
        password = click.prompt("Database Password", hide_input=True, type=Secret)

    state.DB_PASSWORD = password


add_commands(main)


if __name__ == "__main__":
    main()
