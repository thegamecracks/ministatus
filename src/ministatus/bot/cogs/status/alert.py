from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import TYPE_CHECKING, Any, Collection

import discord

from ministatus.bot.db import connect_discord_database_client
from ministatus.bot.dt import utcnow
from ministatus.bot.views import LayoutView
from ministatus.db import Status, StatusAlert, StatusDisplay, StatusQuery, connect

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

ERROR_COLOUR = 0xFF4040
WARNING_COLOUR = 0xFF9640
SUCCESS_COLOUR = 0x5CFF69

log = logging.getLogger(__name__)


async def disable_alert(
    bot: Bot,
    status: Status,
    alert: StatusAlert,
    reason: str,
) -> None:
    log.warning("Alert #%d is invalid: %s", alert.status_alert_id, reason)
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_alert SET enabled_at = NULL, failed_at = $1 "
            "WHERE status_alert_id = $2",
            utcnow(),
            alert.status_alert_id,
        )

    await send_alert_disabled_alert(bot, status, alert, reason)


async def disable_display(
    bot: Bot,
    status: Status,
    display: StatusDisplay,
    reason: str,
) -> None:
    log.warning("Display #%d is invalid: %s", display.message_id, reason)
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_display SET enabled_at = NULL, failed_at = $1 "
            "WHERE message_id = $2",
            utcnow(),
            display.message_id,
        )

    await send_alert_disabled_display(bot, status, display, reason)


async def disable_query(
    bot: Bot,
    status: Status,
    query: StatusQuery,
    reason: str,
) -> None:
    log.warning("Query #%d is invalid: %s", query.status_query_id, reason)
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_query SET enabled_at = NULL, failed_at = $1 "
            "WHERE status_query_id = $2",
            utcnow(),
            query.status_query_id,
        )

    await send_alert_disabled_query(bot, status, query, reason)


async def send_alert_disabled_alert(
    bot: Bot,
    status: Status,
    alert: StatusAlert,
    reason: str,
) -> None:
    status_id = alert.status_id
    async with connect_discord_database_client(bot) as ddc:
        channel = await ddc.get_channel(channel_id=alert.channel_id)
        alert_channels = await ddc.get_bulk_status_alert_channels(
            status_id,
            only_enabled=True,
            type="audit",
        )

    view = AlertDisabledAlert(status, alert, channel, reason)
    await send_alerts(bot, status, alert_channels, view)


async def send_alert_disabled_display(
    bot: Bot,
    status: Status,
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
    view = AlertDisabledDisplay(status, display, message, reason)
    await send_alerts(bot, status, alert_channels, view)


async def send_alert_disabled_query(
    bot: Bot,
    status: Status,
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

    view = AlertDisabledQuery(status, query, reason)
    await send_alerts(bot, status, alert_channels, view)


async def send_alert_downtime_started(bot: Bot, status: Status) -> None:
    status_id = status.status_id
    async with connect_discord_database_client(bot) as ddc:
        alert_channels = await ddc.get_bulk_status_alert_channels(
            status_id,
            only_enabled=True,
            type="downtime",
        )

    view = AlertDowntimeStarted(status)
    await send_alerts(bot, status, alert_channels, view)


async def send_alert_downtime_ended(bot: Bot, status: Status) -> None:
    status_id = status.status_id
    async with connect_discord_database_client(bot) as ddc:
        alert_channels = await ddc.get_bulk_status_alert_channels(
            status_id,
            only_enabled=True,
            type="downtime",
        )

    view = AlertDowntimeEnded(status)
    await send_alerts(bot, status, alert_channels, view)


async def send_alerts(
    bot: Bot,
    status: Status,
    alert_channels: Collection[tuple[StatusAlert, discord.abc.MessageableChannel]],
    view: Alert,
) -> None:
    if not alert_channels:
        return

    log.debug("Sending message to %d status alerts", len(alert_channels))
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = []
            for alert, channel in alert_channels:
                coro = try_send_alert(bot, status, alert, channel, view)
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
        log.warning("One or more status alerts failed", exc_info=eg)
        e = eg.exceptions[0]
        raise e from None


async def try_send_alert(
    bot: Bot,
    status: Status,
    alert: StatusAlert,
    channel: discord.abc.MessageableChannel,
    view: Alert,
) -> None:
    kwargs = view.get_send_kwargs()
    try:
        await channel.send(view=view, **kwargs)
    except discord.Forbidden:
        reason = "Missing permissions to send to channel"
        log.warning("Status alert #%d is invalid: %s", reason)
        await disable_alert(bot, status, alert, reason)
    except discord.NotFound:
        reason = "Channel could not be found"
        log.warning("Status alert #%d is invalid: %s", reason)
        await disable_alert(bot, status, alert, reason)


class Alert(LayoutView):
    container = discord.ui.Container()

    def __init__(self, *, accent_colour: int) -> None:
        super().__init__()
        self.container.accent_colour = accent_colour

    def get_send_kwargs(self) -> dict[str, Any]:
        return {}


class AlertDisabled(Alert):
    def __init__(self, title: str, content: str) -> None:
        super().__init__(accent_colour=ERROR_COLOUR)
        self.container.add_item(discord.ui.TextDisplay(f"## {title}"))
        self.container.add_item(discord.ui.Separator())
        self.container.add_item(discord.ui.TextDisplay(content))


class AlertDisabledAlert(AlertDisabled):
    def __init__(
        self,
        status: Status,
        alert: StatusAlert,
        channel,
        reason: str,
    ) -> None:
        title = f"Alert for {status.label} failed"
        reason = discord.utils.escape_markdown(reason)
        content = (
            f"The alert channel {channel.jump_url} "
            f"has been disabled due to the following reason:\n"
            f"```{reason}```"
        )
        super().__init__(title=title, content=content)


class AlertDisabledDisplay(AlertDisabled):
    def __init__(
        self,
        status: Status,
        display: StatusDisplay,
        message: discord.PartialMessage | int,
        reason: str,
    ) -> None:
        jump_url = str(message) if isinstance(message, int) else message.jump_url
        title = f"Display for {status.label} failed"
        reason = discord.utils.escape_markdown(reason)
        content = (
            f"The display message {jump_url} "
            f"has been disabled due to the following reason:\n"
            f"```{reason}```"
        )
        super().__init__(title=title, content=content)


class AlertDisabledQuery(AlertDisabled):
    def __init__(self, status: Status, query: StatusQuery, reason: str) -> None:
        title = f"Query for {status.label} failed"
        reason = discord.utils.escape_markdown(reason)
        content = (
            f"The {query.type.label} query on {query.address} "
            f"has been disabled due to the following reason:\n"
            f"```{reason}```"
        )
        super().__init__(title=title, content=content)


class AlertDowntime(Alert):
    def __init__(
        self,
        *,
        status: Status,
        accent_colour: int,
        title: str,
        content: str,
    ) -> None:
        super().__init__(accent_colour=accent_colour)

        self.status = status
        self.title = discord.ui.TextDisplay(title)
        self.content = discord.ui.TextDisplay(content)

        if status.thumbnail:
            thumbnail = discord.ui.Thumbnail("attachment://thumbnail.png")
            self.section = discord.ui.Section(accessory=thumbnail)
            self.container.add_item(self.section)
            self.section.add_item(self.title)
            self.section.add_item(self.content)
        else:
            self.section = self.container
            self.section.add_item(self.title)
            self.section.add_item(discord.ui.Separator())
            self.section.add_item(self.content)

    def get_send_kwargs(self) -> dict[str, Any]:
        kwargs = {}
        if self.status.thumbnail:
            thumbnail = discord.File(BytesIO(self.status.thumbnail), "thumbnail.png")
            kwargs["files"] = [thumbnail]
        return kwargs


class AlertDowntimeStarted(AlertDowntime):
    def __init__(self, status: Status) -> None:
        title = f"## {status.label} offline"
        content = [
            f"{status.display_name} has stopped responding to queries.",
            f"**Address:** {status.address}",
        ]
        super().__init__(
            status=status,
            accent_colour=WARNING_COLOUR,
            title=title,
            content="\n".join(content),
        )


class AlertDowntimeEnded(AlertDowntime):
    def __init__(self, status: Status) -> None:
        title = f"## {status.label} online"
        content = [
            f"{status.display_name} is now responding to queries.",
            f"**Address:** {status.address}",
        ]
        super().__init__(
            status=status,
            accent_colour=SUCCESS_COLOUR,
            title=title,
            content="\n".join(content),
        )
