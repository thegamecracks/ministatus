from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Self, cast

import discord
from discord import Interaction, SelectOption
from discord.ui import Select

from ministatus.bot.db import connect_discord_database_client
from ministatus.db import Status, StatusQuery, StatusQueryType

from .book import Book, Page, RenderArgs, get_enabled_text

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

    from .overview import StatusModify


class StatusModifyQueryRow(discord.ui.ActionRow):
    def __init__(self, page: StatusModify) -> None:
        super().__init__()
        self.page = page

    async def render(self) -> Self:
        queries = self.page.status.queries
        query_options = [
            SelectOption(label=f"Query {i}", emoji="🔔", value=str(i - 1))
            for i, query in enumerate(queries, start=1)
        ]
        query_options.append(
            SelectOption(label="Create query...", value="create", emoji="✳️")
        )
        self.queries.options = query_options
        self.queries.placeholder = f"Queries ({len(queries)})"
        return self

    @discord.ui.select()
    async def queries(self, interaction: Interaction, select: Select) -> None:
        value = select.values[0]
        if value == "create":
            modal = CreateStatusQueryModal(self.page.status, self._create_callback)
            await interaction.response.send_modal(modal)
        else:
            query = self.page.status.queries[int(value)]
            assert query is not None
            self.page.book.push(StatusQueryPage(self.page.book, query))
            await self.page.book.edit(interaction)

    async def _create_callback(
        self,
        interaction: Interaction[Bot],
        query: StatusQuery,
    ) -> None:
        self.page.book.push(StatusQueryPage(self.page.book, query))
        await self.page.book.edit(interaction)


class CreateStatusQueryModal(discord.ui.Modal, title="Create Status Query"):
    host = discord.ui.TextInput(
        label="Host",
        placeholder="The server's IP address or hostname",
        min_length=7,
        max_length=255,
    )
    port = discord.ui.TextInput(
        label="Port",
        placeholder="The server port",
        min_length=1,
        max_length=5,
    )
    type = discord.ui.Label(
        text="Query Type",
        component=discord.ui.Select(
            options=[SelectOption(label=t) for t in StatusQueryType],
            placeholder="The game query protocol to use",
        ),
    )
    priority = discord.ui.TextInput(
        label="Priority",
        default="0",
        placeholder="The priority of this query protocol (0 is highest)",
        min_length=1,
        max_length=3,
    )

    def __init__(
        self,
        status: Status,
        callback: Callable[[Interaction[Bot], StatusQuery], Any],
    ) -> None:
        super().__init__()
        self.status = status
        self.callback = callback

    async def on_submit(self, interaction: Interaction) -> None:
        interaction = cast("Interaction[Bot]", interaction)
        assert interaction.guild is not None
        assert isinstance(self.type.component, discord.ui.Select)

        query = StatusQuery(
            status_id=self.status.status_id,
            host=self.host.value,
            port=int(self.port.value),
            type=StatusQueryType(self.type.component.values[0]),
            priority=int(self.priority.value),
        )

        async with connect_discord_database_client(interaction.client) as ddc:
            query = await ddc.client.create_status_query(query)

        self.status.queries.append(query)
        await self.callback(interaction, query)


class StatusQueryPage(Page):
    def __init__(self, book: Book, query: StatusQuery) -> None:
        super().__init__()
        self.book = book
        self.query = query

    async def render(self) -> RenderArgs:
        self.clear_items()
        query = self.query

        self.add_item(discord.ui.TextDisplay(f"## Query {query.host}"))
        self.add_item(discord.ui.Separator())

        lines = [
            f"{get_enabled_text(query.enabled_at)}",
            f"**Host:** {query.host}",
            f"**Port:** {query.port}",
            f"**Type:** {query.type}",
            f"**Priority:** {query.priority}",
        ]

        if query.failed_at is not None:
            dt = discord.utils.format_dt(query.failed_at, "F")
            lines.append(f"**Failing since:** {dt}")

        self.add_item(discord.ui.TextDisplay("\n".join(lines)))

        return RenderArgs()
