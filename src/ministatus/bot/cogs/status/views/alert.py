from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import Interaction, SelectOption
from discord.ui import Select

from ministatus.db import StatusAlert

from .book import Book, Page, RenderArgs, get_enabled_text

if TYPE_CHECKING:
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
            # TODO: create alert modal
            await interaction.response.send_message(
                "This option is not implemented. Sorry!",
                ephemeral=True,
            )
        else:
            alert = discord.utils.get(self.page.status.alerts, channel_id=int(value))
            assert alert is not None
            self.page.book.push(StatusAlertPage(self.page.book, alert))
            await self.page.book.edit(interaction)


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
