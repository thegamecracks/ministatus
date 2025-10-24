import importlib.metadata
import logging

import discord
from discord.ext import commands

from ministatus.bot.cogs import list_extensions

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
