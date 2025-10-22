from click import Group

from ministatus.cli.commands.appdirs import appdirs


def add_commands(group: Group) -> None:
    # TODO: automatic indexing of commands
    group.add_command(appdirs)
