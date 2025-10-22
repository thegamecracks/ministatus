import importlib.metadata
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import discord
from discord.ext import commands

from ministatus.bot.cogs import list_extensions
from ministatus.db import DatabaseClient, SQLiteConnection, connect, connect_client

log = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            help_command=None,
            intents=discord.Intents(
                guilds=True,
                messages=True,
            ),
            strip_after_prefix=True,
        )

    @asynccontextmanager
    async def acquire_db_conn(
        self,
        *,
        transaction: bool = True,
    ) -> AsyncIterator[SQLiteConnection]:
        async with connect() as conn:
            if transaction:
                async with conn.transaction():
                    yield conn
            else:
                yield conn

    @asynccontextmanager
    async def acquire_db_client(
        self,
        *,
        transaction: bool = True,
    ) -> AsyncIterator[DatabaseClient]:
        async with connect_client(transaction=transaction) as client:
            yield client

    async def setup_hook(self) -> None:
        for extension in list_extensions():
            log.info(f"Loading extension {extension}")
            await self.load_extension(extension)
        await self._maybe_load_jishaku()

    async def _maybe_load_jishaku(self) -> None:
        try:
            version = importlib.metadata.version("jishaku")
        except commands.ExtensionNotFound:
            pass
        else:
            await self.load_extension("jishaku")
            log.info("Loaded jishaku extension (v%s)", version)


class Context(commands.Context[Bot]): ...
