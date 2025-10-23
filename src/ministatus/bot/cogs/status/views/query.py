from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import Interaction, SelectOption
from discord.ui import Select

from ministatus.db import StatusQuery

from .book import Book, Page, RenderArgs, get_enabled_text

if TYPE_CHECKING:
    from .overview import StatusModify


class StatusModifyQueryRow(discord.ui.ActionRow):
    def __init__(self, page: StatusModify) -> None:
        super().__init__()
        self.page = page

        query_options = [
            SelectOption(label=f"Query {i}", emoji="🔔", value=str(i - 1))
            for i, query in enumerate(self.page.status.queries, start=1)
        ]
        query_options.append(
            SelectOption(label="Create query...", value="create", emoji="✳️")
        )
        self.queries.options = query_options

    @discord.ui.select(placeholder="Queries")
    async def queries(self, interaction: Interaction, select: Select) -> None:
        value = select.values[0]
        if value == "create":
            # TODO: create query modal
            await interaction.response.send_message(
                "This option is not implemented. Sorry!",
                ephemeral=True,
            )
        else:
            query = self.page.status.queries[int(value)]
            assert query is not None
            self.page.book.push(StatusQueryPage(self.page.book, query))
            await self.page.book.edit(interaction)


class StatusQueryPage(Page):
    def __init__(self, book: Book, query: StatusQuery) -> None:
        super().__init__()
        self.book = book
        self.query = query

    async def render(self) -> RenderArgs:
        query = self.query

        self.add_item(discord.ui.TextDisplay(f"## Query {query.host}"))
        self.add_item(discord.ui.Separator())

        lines = [
            f"{get_enabled_text(query.enabled_at)}",
            f"**Host:** #{query.host}",
            f"**Port:** #{query.port}",
            f"**Type:** #{query.type}",
            f"**Priority:** #{query.priority}",
        ]

        if query.failed_at is not None:
            dt = discord.utils.format_dt(query.failed_at, "F")
            lines.append(f"**Failing since:** {dt}")

        self.add_item(discord.ui.TextDisplay("\n".join(lines)))

        return RenderArgs()
