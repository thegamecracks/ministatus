from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import Interaction, SelectOption
from discord.ui import Select

from ministatus.bot.db import connect_discord_database_client
from ministatus.db import StatusDisplay

from .book import Book, Page, RenderArgs, get_enabled_text

if TYPE_CHECKING:
    from .overview import StatusModify


class StatusModifyDisplayRow(discord.ui.ActionRow):
    def __init__(self, page: StatusModify) -> None:
        super().__init__()
        self.page = page

        display_options = [
            SelectOption(label=f"Display {i}", emoji="🖥️", value=str(display.message_id))
            for i, display in enumerate(self.page.status.displays, start=1)
        ]
        display_options.append(
            SelectOption(label="Create display...", value="create", emoji="✳️")
        )
        self.displays.options = display_options

    @discord.ui.select(placeholder="Displays")
    async def displays(self, interaction: Interaction, select: Select) -> None:
        value = select.values[0]
        if value == "create":
            # TODO: create display context menu
            await interaction.response.send_message(
                "Displays must be created from a message by using the "
                "context menu command, **Create Status Display**.",
                ephemeral=True,
            )
        else:
            display = discord.utils.get(
                self.page.status.displays, message_id=int(value)
            )
            assert display is not None
            self.page.book.push(StatusDisplayPage(self.page.book, display))
            await self.page.book.edit(interaction)


class StatusDisplayPage(Page):
    def __init__(self, book: Book, display: StatusDisplay) -> None:
        super().__init__()
        self.book = book
        self.display = display

    async def render(self) -> RenderArgs:
        display = self.display

        async with connect_discord_database_client(self.book.bot) as ddc:
            message = await ddc.get_message(message_id=display.message_id)

        link = message.jump_url if message is not None else "<deleted message>"

        self.add_item(discord.ui.TextDisplay(f"## Display {link}"))
        self.add_item(discord.ui.Separator())
        self.add_item(
            discord.ui.TextDisplay(
                f"{get_enabled_text(display.enabled_at)}\n"
                f"**Accent colour:** #{display.accent_colour:06X}\n"
                f"**Graph colour:** #{display.graph_colour:06X}\n"
            )
        )

        return RenderArgs()
