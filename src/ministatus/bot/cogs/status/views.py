from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Self, cast

import discord
from discord import Interaction, SelectOption
from discord.ui import Select

from ministatus.db import connect_client
from ministatus.db.models import Status

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot


class PlaceholderView(discord.ui.LayoutView):
    container = discord.ui.Container()

    def __init__(self, user: discord.Member | discord.User) -> None:
        super().__init__()
        self.container.add_item(discord.ui.TextDisplay("## Mini Status"))
        self.container.add_item(discord.ui.Separator())
        self.container.add_item(
            discord.ui.TextDisplay(
                f"Hey there! I'm a placeholder message sent by {user.mention}.\n"
                f"This message isn't doing anything, for now..."
            )
        )


class CancellableView(discord.ui.LayoutView):
    _last_interaction: Interaction[Bot] | None = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        if await super().interaction_check(interaction):
            self.set_last_interaction(interaction)
            return True
        return False

    async def on_timeout(self) -> None:
        if self._last_interaction is None:
            return
        elif self._last_interaction.is_expired():
            return
        elif not self._last_interaction.response.is_done():
            await self._last_interaction.response.defer()

        await self._last_interaction.delete_original_response()

    def set_last_interaction(self, interaction: Interaction) -> None:
        interaction = cast("Interaction[Bot]", interaction)
        self._last_interaction = interaction

    @property
    def last_interaction(self) -> Interaction[Bot]:
        if self._last_interaction is None:
            raise ValueError("Last interaction not set")
        return self._last_interaction


@dataclass(kw_only=True)
class RenderArgs:
    files: list[discord.File] = field(default_factory=list)

    def get_message_kwargs(self) -> dict[str, Any]:
        kwargs = {}
        if self.files:
            kwargs["files"] = self.files
        return kwargs

    def update(self, other: Self) -> None:
        self.files.extend(other.files)


class Book(CancellableView):
    def __init__(self) -> None:
        super().__init__()
        self.pages: list[Page] = []

    def push(self, page: Page) -> None:
        self.pages.append(page)

    def pop(self) -> Page:
        return self.pages.pop()

    async def edit(self, interaction: Interaction, **kwargs) -> None:
        rendered = await self.render()
        kwargs = rendered.get_message_kwargs() | kwargs
        await interaction.response.edit_message(view=self, **kwargs)

    async def send(self, interaction: Interaction, **kwargs) -> None:
        rendered = await self.render()
        kwargs = rendered.get_message_kwargs() | kwargs
        await interaction.response.send_message(view=self, **kwargs)

    async def render(self) -> RenderArgs:
        self.clear_items()

        page = self.pages[-1]
        self.add_item(page)
        rendered = await page.render()
        self.add_item(BookControls(self))
        return rendered

    @property
    def bot(self) -> Bot:
        return self.last_interaction.client

    @property
    def guild(self) -> discord.Guild:
        assert self.last_interaction.guild is not None
        return self.last_interaction.guild


class BookControls(discord.ui.ActionRow):
    def __init__(self, book: Book) -> None:
        super().__init__()
        self.book = book

        self.clear_items()
        if len(book.pages) > 1:
            self.add_item(self.back)
        else:
            self.add_item(self.close)

    @discord.ui.button(label="Back", emoji="⬅️")
    async def back(self, interaction: Interaction, button: discord.ui.Button) -> None:
        self.book.pop()
        await self.book.edit(interaction)

    @discord.ui.button(label="Close", emoji="❌")
    async def close(self, interaction: Interaction, button: discord.ui.Button) -> None:
        assert self.view is not None
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.view.stop()


class Page(discord.ui.Container, ABC):
    @abstractmethod
    async def render(self) -> RenderArgs: ...


def get_enabled_text(enabled_at: datetime.datetime | None) -> str:
    if enabled_at is None:
        return "**Disabled**"
    date = discord.utils.format_dt(enabled_at, "F")
    rel = discord.utils.format_dt(enabled_at, "R")
    return f"**Enabled on:** {date} ({rel})"


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

    @discord.ui.select()
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
        rendered = RenderArgs()
        status = self.status

        self.add_item(discord.ui.Separator())

        summary = discord.ui.TextDisplay(
            f"## {status.label}\n"
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

        # self.add_item(StatusModifyRow(status))

        return rendered
