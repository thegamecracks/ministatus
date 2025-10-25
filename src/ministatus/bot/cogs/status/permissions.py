import discord

from ministatus.bot.errors import ErrorResponse

DEFAULT_REQUIRED_PERMISSIONS = discord.Permissions(
    read_messages=True,
    send_messages=True,
    attach_files=True,
    embed_links=True,
)


async def check_channel_permissions(
    channel: discord.abc.GuildChannel | discord.Thread,
    required: discord.Permissions | None = None,
) -> None:
    perms = channel.permissions_for(channel.guild.me)
    required = required if required is not None else DEFAULT_REQUIRED_PERMISSIONS
    missing = get_missing_permissions(perms, required)
    if missing:
        raise ErrorResponse(
            f"I am missing the following permissions in {channel.mention}: {missing}"
        )


def get_missing_permissions(x: discord.Permissions, y: discord.Permissions) -> str:
    return format_permissions(~(x & y) & y)


def format_permissions(permissions: discord.Permissions) -> str:
    return ", ".join(
        sorted(perm.replace("_", " ").title() for perm, value in permissions if value)
    )
