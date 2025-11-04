from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Callable, Self, cast

import discord
from discord import Interaction, SelectOption
from discord.ui import Button, Select

from ministatus.bot.cogs.status.permissions import check_channel_permissions
from ministatus.bot.db import connect_discord_database_client
from ministatus.bot.dt import utcnow
from ministatus.bot.views import Modal
from ministatus.db import Status, StatusAlert, connect

from .book import (
    Book,
    Page,
    RenderArgs,
    format_enabled,
    format_enabled_at,
    format_failed_at,
)

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

    from .overview import StatusModify


class StatusModifyAlertRow(discord.ui.ActionRow):
    def __init__(self, page: StatusModify) -> None:
        super().__init__()
        self.page = page

    async def render(self) -> Self:
        alerts = self.page.status.alerts
        alert_options = [
            SelectOption(label=f"Alert {i}", emoji="🔔", value=str(alert.channel_id))
            for i, alert in enumerate(alerts, start=1)
        ]
        alert_options.append(
            SelectOption(label="Create alert...", value="create", emoji="✳️")
        )
        self.alerts.options = alert_options
        self.alerts.placeholder = f"Alerts ({len(alerts)})"
        return self

    @discord.ui.select()
    async def alerts(self, interaction: Interaction, select: Select) -> None:
        value = select.values[0]
        if value == "create":
            modal = CreateStatusAlertModal(self.page.status, self._create_callback)
            await interaction.response.send_modal(modal)
        else:
            alert = discord.utils.get(self.page.status.alerts, channel_id=int(value))
            assert alert is not None
            self.page.book.push(StatusAlertPage(self.page.book, alert))
            await self.page.book.edit(interaction)

    async def _create_callback(
        self,
        interaction: Interaction[Bot],
        alert: StatusAlert,
    ) -> None:
        self.page.book.push(StatusAlertPage(self.page.book, alert))
        await self.page.book.edit(interaction)


class CreateStatusAlertModal(Modal, title="Create Status Alert"):
    channel = discord.ui.Label(
        text="Alert Channel",
        component=discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            placeholder="The channel to send alerts to",
        ),
    )
    send_downtime = discord.ui.Label(
        text="Enable downtime messages?",
        description=(
            "Sends a message whenever the server cannot be reached through any "
            "enabled query method."
        ),
        component=discord.ui.Select(
            options=[
                discord.SelectOption(label="Yes", emoji="🟢", value="1", default=True),
                discord.SelectOption(label="No", emoji="🔴", value="0"),
            ],
        ),
    )
    send_audit = discord.ui.Label(
        text="Enable audit messages?",
        description="Sends a message for misconfiguration errors. Should be private.",
        component=discord.ui.Select(
            options=[
                discord.SelectOption(label="Yes", emoji="🟢", value="1", default=True),
                discord.SelectOption(label="No", emoji="🔴", value="0"),
            ],
        ),
    )

    def __init__(
        self,
        status: Status,
        callback: Callable[[Interaction[Bot], StatusAlert], Any],
    ) -> None:
        super().__init__()
        self.status = status
        self.callback = callback

    async def on_submit(self, interaction: Interaction) -> None:
        interaction = cast("Interaction[Bot]", interaction)
        assert interaction.guild is not None
        assert isinstance(self.channel.component, discord.ui.ChannelSelect)
        assert isinstance(self.send_downtime.component, discord.ui.Select)
        assert isinstance(self.send_audit.component, discord.ui.Select)

        channel = self.channel.component.values[0]
        channel = channel.resolve() or await channel.fetch()
        await check_channel_permissions(channel)

        alert = StatusAlert(
            status_alert_id=0,
            status_id=self.status.status_id,
            channel_id=channel.id,
            enabled_at=interaction.created_at,
            send_audit=self.send_audit.component.values[0] == "1",
            send_downtime=self.send_downtime.component.values[0] == "1",
        )

        async with connect_discord_database_client(interaction.client) as ddc:
            await ddc.add_channel(channel)
            alert = await ddc.client.create_status_alert(alert)

        self.status.alerts.append(alert)
        await self.callback(interaction, alert)


class StatusAlertPage(Page):
    def __init__(self, book: Book, alert: StatusAlert) -> None:
        super().__init__()
        self.book = book
        self.alert = alert

    async def render(self) -> RenderArgs:
        self.clear_items()
        alert = self.alert
        channel = self.book.guild.get_channel_or_thread(alert.channel_id)
        mention = channel.mention if channel is not None else "<deleted channel>"

        self.add_item(discord.ui.TextDisplay(f"## Alert {mention}"))
        self.add_item(discord.ui.Separator())

        content = [
            format_enabled_at(alert.enabled_at),
            f"Downtime messages {format_enabled(alert.send_downtime)}",
            f"Error messages {format_enabled(alert.send_audit)}",
            format_failed_at(alert.failed_at),
        ]
        self.add_item(discord.ui.TextDisplay("\n".join(content)))

        self.add_item(await _StatusAlertRow(self).render())

        return RenderArgs()


class _StatusAlertRow(discord.ui.ActionRow):
    def __init__(self, page: StatusAlertPage) -> None:
        super().__init__()
        self.page = page

    async def render(self) -> Self:
        self.clear_items()

        if self.page.alert.enabled_at:
            self.add_item(self.disable)
        else:
            self.add_item(self.enable)

        self.add_item(self.delete)
        return self

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.primary, emoji="🔴")
    async def disable(self, interaction: Interaction, button: Button) -> None:
        enabled_at = None
        await self._set_enabled_at(enabled_at)
        self.page.alert.enabled_at = enabled_at
        await self.page.book.edit(interaction)

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.primary, emoji="🟢")
    async def enable(self, interaction: Interaction, button: Button) -> None:
        enabled_at = utcnow()
        await self._set_enabled_at(enabled_at)
        self.page.alert.enabled_at = enabled_at
        await self.page.book.edit(interaction)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete(self, interaction: Interaction, button: Button) -> None:
        async with connect() as conn:
            await conn.execute(
                "DELETE FROM status_alert WHERE status_alert_id = $1",
                self.page.alert.status_alert_id,
            )

        # HACK: we can't easily propagate deletion up, so let's just terminate the view.
        assert self.view is not None
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.view.stop()

    async def _set_enabled_at(self, enabled_at: datetime.datetime | None) -> None:
        async with connect() as conn:
            await conn.execute(
                "UPDATE status_alert SET enabled_at = $1 WHERE status_alert_id = $2",
                enabled_at,
                self.page.alert.status_alert_id,
            )
