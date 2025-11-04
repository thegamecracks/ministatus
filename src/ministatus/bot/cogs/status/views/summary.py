from __future__ import annotations

import datetime
from io import BytesIO
from typing import TYPE_CHECKING, Protocol

import discord
from discord import Interaction

from ministatus.bot.db import connect_discord_database_client
from ministatus.bot.views import LayoutView
from ministatus.db import Status, StatusAlert, StatusDisplay, StatusQuery

from .book import RenderArgs

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot


class ToggleableState(Protocol):
    enabled_at: datetime.datetime | None
    failed_at: datetime.datetime | None


def _format_state(state: ToggleableState) -> str:
    if state.enabled_at is None and state.failed_at is None:
        return "disabled 🔴"
    elif state.enabled_at is None:
        return "disabled, failed 🔴"
    elif state.failed_at is None:
        return "enabled 🟢"
    else:
        return "enabled, failing 🟡"


def _format_alert(alert: StatusAlert) -> str:
    types = []
    if alert.send_audit:
        types.append("audit")
    if alert.send_downtime:
        types.append("downtime")

    types = ", ".join(types) or "no-op"
    return f"<#{alert.channel_id}> ({types})"


def _format_display(
    display: StatusDisplay,
    message: discord.PartialMessage | None,
) -> str:
    jump_url = display.message_id if message is None else message.jump_url
    return f"{jump_url} ({display.graph_interval})"


def _format_query(query: StatusQuery) -> str:
    return f"{query.type.label} at {query.address}"


class StatusSummaryView(LayoutView):
    def __init__(self, interaction: Interaction[Bot], statuses: list[Status]) -> None:
        super().__init__()
        self.interaction = interaction
        self.statuses = statuses

    async def send(self, interaction: Interaction, **kwargs) -> None:
        rendered = await self.render()
        kwargs = rendered.get_send_kwargs() | kwargs
        await interaction.response.send_message(view=self, **kwargs)

    async def render(self) -> RenderArgs:
        self.clear_items()
        rendered = RenderArgs()

        for status in self.statuses:
            container = _StatusContainer(self.interaction.client, status)
            rendered.update(await container.render())
            self.add_item(container)

        return rendered


class _StatusContainer(discord.ui.Container):
    def __init__(self, bot: Bot, status: Status) -> None:
        super().__init__()
        self.bot = bot
        self.status = status

    async def render(self) -> RenderArgs:
        self.clear_items()
        status = self.status
        rendered = RenderArgs()

        if status.thumbnail:
            filename = f"thumbnail-{status.status_id}.png"
            file = discord.File(BytesIO(status.thumbnail), filename)
            rendered.files.append(file)
            thumbnail = discord.ui.Thumbnail(f"attachment://{filename}")
            section = discord.ui.Section(accessory=thumbnail)
            self.add_item(section)
        else:
            section = self

        content = [
            f"## {status.label}",
            f"**{_format_state(status).title()}**",
        ]

        async with connect_discord_database_client(self.bot) as ddc:
            for i, alert in enumerate(status.alerts, 1):
                line = _format_alert(alert)
                line = f"**Alert {i}** {_format_state(alert)} ⇒ {line}"
                content.append(line)

            for i, display in enumerate(status.displays, 1):
                # NOTE: N+1 query
                message = await ddc.get_message(message_id=display.message_id)
                line = _format_display(display, message)
                line = f"**Display {i}** {_format_state(display)} ⇒ {line}"
                content.append(line)

            for i, query in enumerate(status.queries, 1):
                line = _format_query(query)
                line = f"**Query {i}** {_format_state(query)} ⇒ {line}"
                content.append(line)

        section.add_item(discord.ui.TextDisplay("\n".join(content)))

        return rendered
