import click

from ministatus.appdirs import APP_DIRS


@click.group()
def db() -> None:
    """Manage the application database."""
    # TODO: db command
