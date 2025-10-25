from discord import app_commands
from discord.ext import commands


class ErrorResponse(app_commands.AppCommandError, commands.CommandError):
    """An error message to be sent to the user."""
