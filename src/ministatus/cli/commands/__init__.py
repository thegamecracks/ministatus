import importlib
import logging
import os
import pkgutil
import re
from typing import Iterable

import click
from click import Command, Group

from ministatus.db import Secret, connect_client

log = logging.getLogger(__name__)


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


async def read_token() -> Secret[str]:
    if token := os.getenv("MIST_TOKEN"):
        log.info("Reading token from MIST_TOKEN environment variable")
        return _parse_token(token)

    async with connect_client() as client:
        token = await client.get_setting("token")

    if token is not None:
        return _parse_token(token)

    click.secho("No Discord bot token found in config.")
    click.echo("Your token should look something like this:")
    click.secho(
        "MTI0NjgyNjg0MTIzMTMyNzI3NQ.GTIAZm.x2fbSNuYJgpAocvMM53ROlMC23NixWt-0NOjMc",
        fg="green",
    )
    token = click.prompt("Enter token", hide_input=True, type=_parse_token)

    async with connect_client() as client:
        await client.set_setting("token", token)

    return token


def _parse_token(token: str | Secret[str]) -> Secret[str]:
    if isinstance(token, Secret):
        token = token.get_secret_value()  # Was read from database

    token = token.strip()
    if not re.fullmatch(r"\w+\.\w+\.\S+", token):
        raise ValueError("Invalid token format")
    return Secret(token)
