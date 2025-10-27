import functools
import logging

import discord
from discord import app_commands
from discord.ext import commands

from ministatus.bot.bot import Bot, Context
from ministatus.bot.errors import ErrorResponse

log = logging.getLogger(__name__)


async def on_command_error(ctx: Context, error: commands.CommandError) -> None:
    # original = getattr(error, "original", error)

    # Invalid commands
    if isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.DisabledCommand):
        pass
    # Checks
    elif isinstance(error, commands.NotOwner):
        pass
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"This command is on cooldown for {error.retry_after:.1f}s.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.reply("A check failed to pass before running this command.")
        log_command_error(ctx, error, debug=True)
    # Runtime errors
    elif isinstance(error, ErrorResponse):
        if message := str(error):
            await ctx.reply(message)
    else:
        await ctx.reply("An unknown error occurred while running this command.")
        log_command_error(ctx, error)


def log_command_error(
    ctx: Context,
    error: commands.CommandError,
    *,
    debug: bool = False,
) -> None:
    log.log(
        logging.DEBUG if debug else logging.ERROR,
        f"Exception occurred in command {ctx.command!r}",
        exc_info=error,
    )


async def on_app_command_error(
    interaction: discord.Interaction[Bot],
    error: app_commands.AppCommandError,
) -> None:
    send = functools.partial(interaction_send, interaction)
    # original = getattr(error, "original", error)

    # Invalid commands
    if isinstance(
        error,
        (
            app_commands.CommandNotFound,
            app_commands.CommandSignatureMismatch,
        ),
    ):
        await send("I do not recognize this command anymore. Sorry!")
        log_app_command_error(interaction, error)
    # Checks
    elif isinstance(error, app_commands.CommandOnCooldown):
        await send(f"This command is on cooldown for {error.retry_after:.1f}s.")
    elif isinstance(error, app_commands.CheckFailure):
        await send("A check failed to pass before running this command.")
        log_app_command_error(interaction, error, debug=True)
    # Runtime errors
    elif isinstance(error, ErrorResponse):
        if message := str(error):
            await send(message)
    else:
        await send("An unknown error occurred while running this command.")
        log_app_command_error(interaction, error)


def log_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
    *,
    debug: bool = False,
) -> None:
    command = interaction.command.qualified_name if interaction.command else None
    log.log(
        logging.DEBUG if debug else logging.ERROR,
        f"Exception occurred in application command {command!r}",
        exc_info=error,
    )


async def interaction_send(interaction: discord.Interaction, *args, **kwargs) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(*args, **kwargs)
    else:
        kwargs.setdefault("ephemeral", True)
        await interaction.response.send_message(*args, **kwargs)


class Errors(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.setup_events()

    async def cog_unload(self) -> None:
        self.teardown_events()

    def setup_events(self) -> None:
        self._old_command_error = self.bot.on_command_error
        self.bot.on_command_error = on_command_error  # type: ignore

        self._old_tree_error = self.bot.tree.on_error
        self.bot.tree.error(on_app_command_error)

    def teardown_events(self) -> None:
        self.bot.on_command_error = self._old_command_error
        self.bot.tree.error(self._old_tree_error)


async def setup(bot: Bot):
    await bot.add_cog(Errors(bot))
