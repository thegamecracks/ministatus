import logging

import click

from ministatus import __version__
from ministatus.logging import setup_logging

log = logging.getLogger(__name__)


CONTEXT_SETTINGS = dict(
    help_option_names=("-h", "--help"),
)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("-v", "--verbose", count=True)
@click.version_option(__version__, "-V", "--version")
def main(verbose: int) -> None:
    """A Discord bot for managing game server status embeds."""
    setup_logging(verbose=verbose)


if __name__ == "__main__":
    main()
