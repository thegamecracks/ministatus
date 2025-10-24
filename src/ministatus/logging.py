import datetime
import json
import logging
import logging.handlers
import os
import sys
from typing import Any

from ministatus.appdirs import APP_DIRS

DATEFMT = "%Y-%m-%d %H:%M:%S"
LOG_RECORD_ATTRIBUTES = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",  # cached by formatException()
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


def setup_logging(*, verbose: int) -> None:
    assert __package__ is not None

    if verbose <= 0:
        root_level = logging.INFO
        pkg_level = logging.NOTSET
    elif verbose <= 1:
        root_level = logging.INFO
        pkg_level = logging.DEBUG
    else:
        root_level = logging.DEBUG
        pkg_level = logging.NOTSET

    stream = create_stream_handler()
    jsonl = create_jsonl_handler()

    root = logging.getLogger()
    root.setLevel(root_level)
    root.addHandler(stream)
    root.addHandler(jsonl)

    # NOTE: Logging propagation only applies to handlers and not filters,
    #       so root.addFilter() won't catch logs from all loggers.
    #       We need to add filters directly to each package's logger.
    logging.getLogger("discord.client").addFilter(
        lambda r: not r.getMessage().startswith("PyNaCl")
    )

    pkg = logging.getLogger(__package__.partition(".")[0])
    pkg.setLevel(pkg_level)


def create_stream_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler()

    # Derived from discord.utils.setup_logging()
    if stream_supports_colour(handler.stream):
        formatter = ColourFormatter()
    else:
        formatter = logging.Formatter(
            "[{asctime}] [{levelname:<8}] {name}: {message}",
            DATEFMT,
            style="{",
        )

    handler.setFormatter(formatter)
    return handler


def stream_supports_colour(stream: Any) -> bool:
    is_a_tty = hasattr(stream, "isatty") and stream.isatty()

    # Pycharm and Vscode support colour in their inbuilt editors
    if "PYCHARM_HOSTED" in os.environ or os.environ.get("TERM_PROGRAM") == "vscode":
        return is_a_tty

    if sys.platform != "win32":
        # Docker does not consistently have a tty attached to it
        return is_a_tty or is_docker()

    # ANSICON checks for things like ConEmu
    # WT_SESSION checks if this is Windows Terminal
    return is_a_tty and ("ANSICON" in os.environ or "WT_SESSION" in os.environ)


def is_docker() -> bool:
    path = "/proc/self/cgroup"
    return os.path.exists("/.dockerenv") or (
        os.path.isfile(path) and any("docker" in line for line in open(path))
    )


class ColourFormatter(logging.Formatter):
    # ANSI codes are a bit weird to decipher if you're unfamiliar with them, so here's a refresher
    # It starts off with a format like \x1b[XXXm where XXX is a semicolon separated list of commands
    # The important ones here relate to colour.
    # 30-37 are black, red, green, yellow, blue, magenta, cyan and white in that order
    # 40-47 are the same except for the background
    # 90-97 are the same but "bright" foreground
    # 100-107 are the same as the bright ones but for the background.
    # 1 means bold, 2 means dim, 0 means reset, and 4 means underline.

    LEVEL_COLOURS = [
        (logging.DEBUG, "\x1b[40;1m"),
        (logging.INFO, "\x1b[34;1m"),
        (logging.WARNING, "\x1b[33;1m"),
        (logging.ERROR, "\x1b[31m"),
        (logging.CRITICAL, "\x1b[41m"),
    ]

    FORMATS = {
        level: logging.Formatter(
            f"\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-8s\x1b[0m \x1b[35m%(name)s\x1b[0m %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        for level, colour in LEVEL_COLOURS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno)
        if formatter is None:
            formatter = self.FORMATS[logging.DEBUG]

        # Override the traceback to always print in red
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f"\x1b[31m{text}\x1b[0m"

        output = formatter.format(record)

        # Remove the cache layer
        record.exc_text = None
        return output


def create_jsonl_handler() -> logging.FileHandler:
    handler = logging.handlers.RotatingFileHandler(
        filename=APP_DIRS.user_log_path / f"{APP_DIRS.appname}.jsonl",
        maxBytes=5_000_000,
        backupCount=3,
    )
    handler.setFormatter(JSONFormatter())
    return handler


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = self._prepare_record(record)
        return json.dumps(data, default=str)

    def _prepare_record(self, record: logging.LogRecord) -> dict[str, Any]:
        data = {}

        for k, v in vars(record).items():
            if k not in LOG_RECORD_ATTRIBUTES:
                data[k] = v

        created = datetime.datetime.fromtimestamp(
            record.created,
            tz=datetime.timezone.utc,
        )

        data["level"] = record.levelname
        data["created"] = created.isoformat()
        data["message"] = record.getMessage()

        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            data["stack_info"] = self.formatStack(record.stack_info)

        return data
