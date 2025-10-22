from click import Group

from ministatus.cli.commands.appdirs import appdirs
from ministatus.cli.commands.config import config
from ministatus.cli.commands.db import db


def add_commands(group: Group) -> None:
    # TODO: automatic indexing of commands
    group.add_command(appdirs)
    group.add_command(config)
    group.add_command(db)
