from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
from discord import Interaction, SelectOption
from discord.ui import Button, Select

from ministatus.bot.db import connect_discord_database_client
from ministatus.db import StatusDisplay, connect

from .book import Book, Page, RenderArgs, get_enabled_text

if TYPE_CHECKING:
    from .overview import StatusModify


class StatusModifyDisplayRow(discord.ui.ActionRow):
    def __init__(self, page: StatusModify) -> None:
        super().__init__()
        self.page = page

    async def render(self) -> Self:
        displays = self.page.status.displays
        display_options = [
            SelectOption(label=f"Display {i}", emoji="🖥️", value=str(display.message_id))
            for i, display in enumerate(displays, start=1)
        ]
        display_options.append(
            SelectOption(label="Create display...", value="create", emoji="✳️")
        )
        self.displays.options = display_options
        self.displays.placeholder = f"Displays ({len(displays)})"
        return self

    @discord.ui.select()
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
        self.clear_items()
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
        self.add_item(await _StatusDisplayRow(self).render())

        return RenderArgs()


class _StatusDisplayRow(discord.ui.ActionRow):
    def __init__(self, page: StatusDisplayPage) -> None:
        super().__init__()
        self.page = page

    async def render(self) -> Self:
        self.clear_items()

        if self.page.display.enabled_at:
            self.add_item(self.disable)
        else:
            self.add_item(self.enable)

        self.add_item(self.delete)
        return self

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.primary, emoji="🔴")
    async def disable(self, interaction: Interaction, button: Button) -> None:
        enabled_at = None
        await self._set_enabled_at(enabled_at)
        self.page.display.enabled_at = enabled_at
        await self.page.book.edit(interaction)

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.primary, emoji="🟢")
    async def enable(self, interaction: Interaction, button: Button) -> None:
        enabled_at = datetime.datetime.now(datetime.timezone.utc)
        await self._set_enabled_at(enabled_at)
        self.page.display.enabled_at = enabled_at
        await self.page.book.edit(interaction)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete(self, interaction: Interaction, button: Button) -> None:
        async with connect() as conn:
            await conn.execute(
                "DELETE FROM status_display WHERE message_id = $1",
                self.page.display.message_id,
            )

        # HACK: we can't easily propagate deletion up, so let's just terminate the view.
        assert self.view is not None
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.view.stop()

    async def _set_enabled_at(self, enabled_at: datetime.datetime | None) -> None:
        async with connect() as conn:
            await conn.execute(
                "UPDATE status_display SET enabled_at = $1 WHERE message_id = $2",
                enabled_at,
                self.page.display.message_id,
            )
