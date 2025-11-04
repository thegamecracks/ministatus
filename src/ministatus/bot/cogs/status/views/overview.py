from __future__ import annotations

import datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any, Callable, Self, cast

import discord
from discord import Interaction, SelectOption
from discord.ui import Button, Select

from ministatus.bot.db import connect_discord_database_client
from ministatus.bot.dt import utcnow
from ministatus.bot.errors import ErrorResponse
from ministatus.bot.views import Modal
from ministatus.db import Status, connect, connect_client

from .book import Book, Page, RenderArgs, format_enabled_at, format_failed_at
from .alert import StatusModifyAlertRow
from .display import StatusModifyDisplayRow
from .query import StatusModifyQueryRow

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot


class StatusManageView(Book):
    def __init__(self, interaction: Interaction[Bot], statuses: list[Status]) -> None:
        super().__init__()
        self.set_last_interaction(interaction)
        self.statuses = statuses
        self.push(StatusOverview(self, self.statuses))


class StatusOverview(Page):
    def __init__(self, book: Book, statuses: list[Status]) -> None:
        super().__init__()
        self.book = book
        self.select = StatusOverviewSelect(statuses)

    async def render(self) -> RenderArgs:
        self.clear_items()
        self.add_item(self.select)
        await self.select.render()
        return RenderArgs()


class StatusOverviewSelect(discord.ui.ActionRow):
    parent: StatusOverview  # type: ignore

    def __init__(self, statuses: list[Status]) -> None:
        super().__init__()
        self.statuses = statuses

    async def render(self) -> None:
        options = [
            SelectOption(
                label=status.label,
                emoji="🟢" if status.enabled_at else "🔴",
                description="Enabled" if status.enabled_at else "Disabled",
                value=str(status.status_id),
            )
            for status in self.statuses
        ]

        options.append(
            SelectOption(label="Create status...", emoji="✳️", value="create")
        )
        self.on_select.options = options

    @discord.ui.select(placeholder="Select a server status")
    async def on_select(self, interaction: Interaction[Bot], select: Select) -> None:
        value = select.values[0]
        if value == "create":
            modal = CreateStatusModal(self._create_callback)
            await interaction.response.send_modal(modal)
        else:
            status = discord.utils.get(self.statuses, status_id=int(value))
            assert status is not None
            self.parent.book.push(StatusModify(self.parent.book, status))
            await self.parent.book.edit(interaction)

    async def _create_callback(
        self,
        interaction: Interaction[Bot],
        status: Status,
    ) -> None:
        self.statuses.append(status)
        self.parent.book.push(StatusModify(self.parent.book, status))
        await self.parent.book.edit(interaction)


class CreateStatusModal(Modal, title="Create Status"):
    label = discord.ui.TextInput(
        label="Label",
        placeholder="A useful label for your new status",
        min_length=1,
        max_length=100,
    )

    def __init__(
        self,
        callback: Callable[[Interaction[Bot], Status], Any],
    ) -> None:
        super().__init__()
        self.callback = callback

    async def on_submit(self, interaction: Interaction) -> None:
        interaction = cast("Interaction[Bot]", interaction)
        assert interaction.guild is not None

        label = discord.utils.remove_markdown(self.label.value)
        label, _, _ = label.partition("\n")
        label = label.strip()
        if not label:
            raise ErrorResponse("Label not allowed. Please try again!")

        status = Status(
            status_id=0,
            guild_id=interaction.guild.id,
            label=label,
            enabled_at=interaction.created_at,
        )

        async with connect_client() as client:
            status = await client.create_status(status)

        await self.callback(interaction, status)


class StatusModify(Page):
    def __init__(self, book: Book, status: Status) -> None:
        super().__init__()
        self.book = book
        self.status = status

    async def render(self) -> RenderArgs:
        self.clear_items()
        rendered = RenderArgs()
        status = self.status

        if status.thumbnail is not None:
            file = discord.File(BytesIO(status.thumbnail), "thumbnail.png")
            rendered.files.append(file)

            thumbnail = discord.ui.Thumbnail("attachment://thumbnail.png")
            section = discord.ui.Section(accessory=thumbnail)
            self.add_item(section)
        else:
            section = self

        section.add_item(discord.ui.TextDisplay(f"## {status.label}"))
        if section == self:
            self.add_item(discord.ui.Separator())

        content = [
            format_enabled_at(status.enabled_at),
            f"**Server name:** {status.title}",
            f"**Address:** {status.address}",
            format_failed_at(status.failed_at),
        ]
        section.add_item(discord.ui.TextDisplay("\n".join(content)))

        self.add_item(await StatusModifyAlertRow(self).render())
        self.add_item(await StatusModifyDisplayRow(self).render())
        self.add_item(await StatusModifyQueryRow(self).render())
        self.add_item(await _StatusModifyRow(self).render())

        return rendered


class _StatusModifyRow(discord.ui.ActionRow):
    def __init__(self, page: StatusModify) -> None:
        super().__init__()
        self.page = page

    async def render(self) -> Self:
        self.clear_items()

        if self.page.status.enabled_at:
            self.add_item(self.disable)
        else:
            self.add_item(self.enable)

        self.add_item(self.delete)
        return self

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.primary, emoji="🔴")
    async def disable(self, interaction: Interaction, button: Button) -> None:
        enabled_at = None
        await self._set_enabled_at(enabled_at)
        self.page.status.enabled_at = enabled_at
        await self.page.book.edit(interaction)

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.primary, emoji="🟢")
    async def enable(self, interaction: Interaction, button: Button) -> None:
        enabled_at = utcnow()
        await self._set_enabled_at(enabled_at)
        self.page.status.enabled_at = enabled_at
        await self.page.book.edit(interaction)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete(self, interaction: Interaction, button: Button) -> None:
        bot = cast("Bot", interaction.client)
        status_id = self.page.status.status_id

        async with connect_discord_database_client(bot, transaction="write") as ddc:
            conn = ddc.client.conn
            messages = [
                row["message_id"]
                for row in await conn.fetch(
                    "SELECT message_id FROM status_display WHERE status_id = $1",
                    status_id,
                )
            ]
            # NOTE: N+1 query
            messages = [await ddc.get_message(message_id=m) for m in messages]
            messages = [m for m in messages if m is not None]
            await conn.execute("DELETE FROM status WHERE status_id = $1", status_id)

        # HACK: we can't easily propagate deletion up, so let's just terminate the view.
        assert self.view is not None
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.view.stop()

        for m in messages:
            await m.delete(delay=0)

    async def _set_enabled_at(self, enabled_at: datetime.datetime | None) -> None:
        async with connect() as conn:
            await conn.execute(
                "UPDATE status SET enabled_at = $1 WHERE status_id = $2",
                enabled_at,
                self.page.status.status_id,
            )
