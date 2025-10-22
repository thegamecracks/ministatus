import logging

import click

from ministatus import __version__
from ministatus.logging import setup_logging

log = logging.getLogger(__name__)


@click.group()
@click.option("-v", "--verbose", count=True)
@click.version_option(__version__, "-V", "--version")
def main(verbose: int) -> None:
    setup_logging(verbose=verbose)


if __name__ == "__main__":
    main()
