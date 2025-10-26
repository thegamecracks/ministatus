from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Collection

import discord

from ministatus.bot.db import connect_discord_database_client
from ministatus.bot.dt import utcnow
from ministatus.bot.views import LayoutView
from ministatus.db import StatusAlert, StatusDisplay, StatusQuery, connect

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

log = logging.getLogger(__name__)


async def disable_alert(bot: Bot, alert: StatusAlert, reason: str) -> None:
    log.warning("Alert #%d is invalid: %s", alert.status_alert_id, reason)
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_alert SET enabled_at = NULL, failed_at = $1 "
            "WHERE status_alert_id = $2",
            utcnow(),
            alert.status_alert_id,
        )

    await send_alert_disabled_alert(bot, alert, reason)


async def disable_display(bot: Bot, display: StatusDisplay, reason: str) -> None:
    log.warning("Display #%d is invalid: %s", display.message_id, reason)
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_display SET enabled_at = NULL, failed_at = $1 "
            "WHERE message_id = $2",
            utcnow(),
            display.message_id,
        )

    await send_alert_disabled_display(bot, display, reason)


async def disable_query(bot: Bot, query: StatusQuery, reason: str) -> None:
    log.warning("Query #%d is invalid: %s", query.status_query_id, reason)
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_query SET enabled_at = NULL, failed_at = $1 "
            "WHERE status_query_id = $2",
            utcnow(),
            query.status_query_id,
        )

    await send_alert_disabled_query(bot, query, reason)


async def send_alert_disabled_alert(
    bot: Bot,
    alert: StatusAlert,
    reason: str,
) -> None:
    status_id = alert.status_id
    async with connect_discord_database_client(bot) as ddc:
        alert_channels = await ddc.get_bulk_status_alert_channels(
            status_id,
            only_enabled=True,
            type="audit",
        )

    view = AlertDisabledAlert(alert, reason)
    await send_alerts(bot, alert_channels, view)


async def send_alert_disabled_display(
    bot: Bot,
    display: StatusDisplay,
    reason: str,
) -> None:
    status_id = display.status_id
    async with connect_discord_database_client(bot) as ddc:
        message = await ddc.get_message(message_id=display.message_id)
        alert_channels = await ddc.get_bulk_status_alert_channels(
            status_id,
            only_enabled=True,
            type="audit",
        )

    message = message or display.message_id
    view = AlertDisabledDisplay(display, message, reason)
    await send_alerts(bot, alert_channels, view)


async def send_alert_disabled_query(
    bot: Bot,
    query: StatusQuery,
    reason: str,
) -> None:
    status_id = query.status_id
    async with connect_discord_database_client(bot) as ddc:
        alert_channels = await ddc.get_bulk_status_alert_channels(
            status_id,
            only_enabled=True,
            type="audit",
        )

    view = AlertDisabledQuery(query, reason)
    await send_alerts(bot, alert_channels, view)


async def send_alerts(
    bot: Bot,
    alert_channels: Collection[tuple[StatusAlert, discord.abc.MessageableChannel]],
    view: LayoutView,
) -> None:
    if not alert_channels:
        return

    log.debug("Sending message to %d status alerts", len(alert_channels))
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = []
            for alert, channel in alert_channels:
                coro = try_send_alert(bot, alert, channel, view)
                tasks.append(tg.create_task(coro))

            # Let all tasks run first, and collect any errors to raise afterwards
            await asyncio.wait(tasks)

        exceptions = [e for t in tasks if (e := t.exception()) is not None]
        if exceptions:
            raise BaseExceptionGroup(
                f"{len(exceptions)} query job(s) failed", exceptions
            )

    except* (discord.DiscordServerError, discord.RateLimited) as eg:
        # Ergh, drop all other exceptions so tasks.loop() can handle it
        log.warning("One or more status alerts failed: %s", exc_info=eg)
        e = eg.exceptions[0]
        raise e from None


async def try_send_alert(
    bot: Bot,
    alert: StatusAlert,
    channel: discord.abc.MessageableChannel,
    view: LayoutView,
) -> None:
    try:
        await channel.send(view=view)
    except discord.Forbidden:
        reason = "Missing permissions to send to channel"
        log.warning("Status alert #%d is invalid: %s", reason)
        await disable_alert(bot, alert, reason)
    except discord.NotFound:
        reason = "Channel could not be found"
        log.warning("Status alert #%d is invalid: %s", reason)
        await disable_alert(bot, alert, reason)


class Alert(LayoutView):
    container = discord.ui.Container()

    def __init__(self, *, accent_colour: int, title: str, content: str) -> None:
        super().__init__()
        self.container.accent_colour = accent_colour
        self.container.add_item(discord.ui.TextDisplay(f"## {title}"))
        self.container.add_item(discord.ui.Separator())
        self.container.add_item(discord.ui.TextDisplay(content))


class AlertDisabled(Alert):
    def __init__(self, title: str, content: str) -> None:
        super().__init__(accent_colour=0xFF4040, title=title, content=content)


class AlertDisabledAlert(AlertDisabled):
    def __init__(self, alert: StatusAlert, reason: str) -> None:
        title = f"Alert <#{alert.channel_id}> failed"
        reason = discord.utils.escape_markdown(reason)
        content = (
            f"The alert channel has been disabled due to the following reason:\n"
            f"```{reason}```"
        )
        super().__init__(title=title, content=content)


class AlertDisabledDisplay(AlertDisabled):
    def __init__(
        self,
        display: StatusDisplay,
        message: discord.PartialMessage | int,
        reason: str,
    ) -> None:
        jump_url = str(message) if isinstance(message, int) else message.jump_url
        title = f"Display {jump_url} failed"
        reason = discord.utils.escape_markdown(reason)
        content = (
            f"Display {jump_url} has been disabled due to the following reason:\n"
            f"```{reason}```"
        )
        super().__init__(title=title, content=content)


class AlertDisabledQuery(AlertDisabled):
    def __init__(self, query: StatusQuery, reason: str) -> None:
        title = f"Query {query.host} failed"
        reason = discord.utils.escape_markdown(reason)
        content = (
            f"The query for {query.host}:{query.game_port}:{query.query_port} "
            f"has been disabled due to the following reason:\n"
            f"```{reason}```"
        )
        super().__init__(title=title, content=content)
