"""A Discord bot for managing game server status embeds."""

import argparse
import sys
from dataclasses import dataclass
from typing import Self, Type

from ministatus import __version__
from ministatus.cli.command import Command, clean_doc


@dataclass(kw_only=True)
class Config:
    args: argparse.Namespace
    command_cls: Type[Command]
    verbose: int

    @classmethod
    def parse_args(cls) -> Self:
        assert __package__ is not None
        parser = argparse.ArgumentParser(
            description=clean_doc(__doc__),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog=__package__.partition(".")[0],
        )
        parser.suggest_on_error = True  # type: ignore  # available in 3.14
        parser.add_argument(
            "-V",
            "--version",
            action="version",
            version=f"%(prog)s {__version__}",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="count",
            default=0,
            help="Increase logging verbosity",
        )
        parser.set_defaults(command=None)

        # subparsers = parser.add_subparsers()
        # commands = sorted(cls.COMMANDS, key=lambda t: t.__name__.lower())
        # for command_cls in commands:
        #     command_cls.register(subparsers)

        args = parser.parse_args()
        if args.command is None:
            parser.print_help()
            sys.exit(1)

        return cls.from_args(args)

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Self:
        return cls(
            args=args,
            command_cls=args.command,
            verbose=args.verbose,
        )

    def invoke(self) -> None:
        command = self.command_cls.from_config(self)
        command.invoke()
