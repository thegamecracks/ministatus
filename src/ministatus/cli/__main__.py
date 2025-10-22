import logging
import sys

from ministatus.cli.config import Config
from ministatus.cli.errors import CommandError
from ministatus.logging import setup_logging

log = logging.getLogger(__name__)


def main() -> None:
    try:
        config = Config.parse_args()
        setup_logging(verbose=config.verbose)
        try_invoke(config)
    except EOFError:
        print()
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except Exception as e:
        log.exception(e)
        sys.exit(1)

def try_invoke(config: Config) -> None:
    try:
        config.invoke()
    except CommandError as e:
        if config.verbose:
            log.exception(e)
        else:
            log.error("%s\n(To show full traceback, use -v/--verbose)", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
