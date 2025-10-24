from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, cast

import discord
from discord import Interaction, SelectOption
from discord.ui import Select

from ministatus.db import Status, connect_client

from .book import Book, Page, RenderArgs, get_enabled_text
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


class CreateStatusModal(discord.ui.Modal, title="Create Status"):
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

        label = discord.utils.remove_markdown(self.label.value).splitlines()[0].strip()
        if not label:
            content = "Label not allowed. Please try again!"
            await interaction.response.send_message(content, ephemeral=True)

        status = Status(
            status_id=0,
            guild_id=interaction.guild.id,
            label=label,
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

        self.add_item(discord.ui.TextDisplay(f"## {status.label}"))
        self.add_item(discord.ui.Separator())

        summary = discord.ui.TextDisplay(
            f"{get_enabled_text(status.enabled_at)}\n"
            f"**Server name:** {status.title}\n"
            f"**Address:** {status.address}\n"
        )

        if status.thumbnail is not None:
            rendered.files.append(discord.File(status.thumbnail, "thumbnail.png"))
            accessory = discord.ui.Thumbnail("attachment://thumbnail.png")
            section = discord.ui.Section(summary, accessory=accessory)
            self.add_item(section)
        else:
            self.add_item(summary)

        self.add_item(await StatusModifyAlertRow(self).render())
        self.add_item(await StatusModifyDisplayRow(self).render())
        self.add_item(await StatusModifyQueryRow(self).render())

        return rendered
