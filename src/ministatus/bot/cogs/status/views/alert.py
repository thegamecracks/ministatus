from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, cast

import discord
from discord import Interaction, SelectOption
from discord.ui import Select

from ministatus.bot.db import connect_discord_database_client
from ministatus.db import Status, StatusAlert

from .book import Book, Page, RenderArgs, get_enabled_text

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

    from .overview import StatusModify


class StatusModifyAlertRow(discord.ui.ActionRow):
    def __init__(self, page: StatusModify) -> None:
        super().__init__()
        self.page = page

        alert_options = [
            SelectOption(label=f"Alert {i}", emoji="🔔", value=str(alert.channel_id))
            for i, alert in enumerate(self.page.status.alerts, start=1)
        ]
        alert_options.append(
            SelectOption(label="Create alert...", value="create", emoji="✳️")
        )
        self.alerts.options = alert_options

    @discord.ui.select(placeholder="Alerts")
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
        self.page.status.alerts.append(alert)
        self.page.book.push(StatusAlertPage(self.page.book, alert))
        await self.page.book.edit(interaction)


class CreateStatusAlertModal(discord.ui.Modal, title="Create Status Alert"):
    channel = discord.ui.Label(
        text="Alert Channel",
        component=discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            placeholder="The channel to send alerts to",
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

        channel = self.channel.component.values[0]
        alert = StatusAlert(
            status_id=self.status.status_id,
            channel_id=channel.id,
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
        alert = self.alert
        channel = self.book.guild.get_channel_or_thread(alert.channel_id)
        mention = channel.mention if channel is not None else "<deleted channel>"

        self.add_item(discord.ui.TextDisplay(f"## Alert {mention}"))
        self.add_item(discord.ui.Separator())
        self.add_item(discord.ui.TextDisplay(get_enabled_text(alert.enabled_at)))

        return RenderArgs()
