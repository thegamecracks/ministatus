import importlib
import pkgutil
from typing import Iterable

from click import Command, Group


def add_commands(group: Group) -> None:
    for info in pkgutil.iter_modules(__path__):
        module_name = info.name
        module = importlib.import_module(f".{module_name}", package=__name__)

        members = getattr(module, "__all__", None)
        if members is None:
            members = getattr(module, module_name, None)
        if not isinstance(members, Iterable):
            members = [members]

        commands = [m for m in members if isinstance(m, Command)]
        for cmd in commands:
            group.add_command(cmd)
