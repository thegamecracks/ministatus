import click

from ministatus.appdirs import APP_DIRS


@click.command()
def appdirs() -> None:
    """Show directories used by this application."""
    click.echo(f"user_data_path    = {APP_DIRS.user_data_path}")
    click.echo(f"user_log_path     = {APP_DIRS.user_log_path}")
