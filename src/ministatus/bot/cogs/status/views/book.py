from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self, cast

import discord
from discord import Interaction

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot


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
