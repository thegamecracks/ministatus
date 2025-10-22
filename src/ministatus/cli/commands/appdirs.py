import click

from ministatus.appdirs import APP_DIRS, DB_PATH


@click.command()
def appdirs() -> None:
    """Show directories and important files used by this application."""
    click.echo(f"user_data_path    = {APP_DIRS.user_data_path}")
    click.echo(f"user_log_path     = {APP_DIRS.user_log_path}")
    click.echo(f"DB_PATH           = {DB_PATH}")
