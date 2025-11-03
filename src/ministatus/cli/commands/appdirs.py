import click

from ministatus.appdirs import APP_DIRS


@click.command()
def appdirs() -> None:
    """Show directories and important files used by this application."""

    def echo_appdirs_path(attr: str) -> None:
        value = getattr(APP_DIRS, attr)
        name = click.style(format(attr, "<17"), fg="yellow")
        value = click.style(value, fg="green")
        click.secho(f"{name} = {value}")

    echo_appdirs_path("user_data_path")
    echo_appdirs_path("user_log_path")
