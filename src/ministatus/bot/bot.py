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

        invite_link = self.get_standard_invite()
        log.info("Invite link:\n%s", invite_link)

    async def _maybe_load_jishaku(self) -> None:
        try:
            version = importlib.metadata.version("jishaku")
        except commands.ExtensionNotFound:
            pass
        else:
            await self.load_extension("jishaku")
            log.info("Loaded jishaku extension (v%s)", version)

    def get_standard_invite(self) -> str:
        assert self.application is not None
        return discord.utils.oauth_url(
            self.application.id,
            scopes=("bot",),
            permissions=discord.Permissions(
                read_messages=True,
                send_messages=True,
                send_messages_in_threads=True,
                embed_links=True,
                attach_files=True,
            ),
        )


class Context(commands.Context[Bot]): ...
