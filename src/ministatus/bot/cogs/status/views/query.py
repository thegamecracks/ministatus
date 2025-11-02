from __future__ import annotations

import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Self,
    TypeAlias,
    assert_never,
    cast,
)

import discord
from discord import Interaction, SelectOption
from discord.ui import Button, Select

from ministatus.bot.db import connect_discord_database_client
from ministatus.bot.dt import utcnow
from ministatus.bot.views import LayoutView, Modal
from ministatus.db import Status, StatusQuery, StatusQueryType, connect

from .book import Book, Page, RenderArgs, format_enabled_at, format_failed_at

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

    from .overview import StatusModify

_CreateCallback: TypeAlias = (
    "Callable[[Interaction[Bot], StatusQuery | None], Awaitable[Any]]"
)


def get_default_ports(type: StatusQueryType) -> tuple[int, int | None]:
    if type == StatusQueryType.ARMA_3:
        return 2302, None
    elif type == StatusQueryType.ARMA_REFORGER:
        return 2001, 17777
    elif type == StatusQueryType.MINECRAFT_BEDROCK:
        return 19132, None
    elif type == StatusQueryType.MINECRAFT_JAVA:
        return 25565, None
    elif type == StatusQueryType.SOURCE:
        return 27015, 27015
    elif type == StatusQueryType.PROJECT_ZOMBOID:
        return 16261, None
    else:
        assert_never(type)


class StatusModifyQueryRow(discord.ui.ActionRow):
    def __init__(self, page: StatusModify) -> None:
        super().__init__()
        self.page = page

    async def render(self) -> Self:
        queries = self.page.status.queries
        query_options = [
            SelectOption(label=f"Query {i}", emoji="📡", value=str(i - 1))
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
            modal = CreateStatusQueryTypeModal(self.page.status, self._create_callback)
            await interaction.response.send_modal(modal)
        else:
            query = self.page.status.queries[int(value)]
            assert query is not None
            self.page.book.push(StatusQueryPage(self.page.book, query))
            await self.page.book.edit(interaction)

    async def _create_callback(
        self,
        interaction: Interaction[Bot],
        query: StatusQuery | None,
    ) -> None:
        if query is not None:
            self.page.book.push(StatusQueryPage(self.page.book, query))
        await self.page.book.edit(interaction)


class CreateStatusQueryTypeModal(Modal, title="Create Status Query"):
    type = discord.ui.Label(
        text="Query Type",
        component=discord.ui.Select(
            options=sorted(
                (SelectOption(label=t.label, value=t) for t in StatusQueryType),
                key=lambda o: o.label.lower(),
            ),
            placeholder="The game query protocol to use",
        ),
    )
    host = discord.ui.TextInput(
        label="Host",
        placeholder="The server's IP address or hostname",
        min_length=7,
        max_length=255,
    )

    def __init__(
        self,
        status: Status,
        callback: _CreateCallback,
    ) -> None:
        super().__init__()
        self.status = status
        self.callback = callback

    async def on_submit(self, interaction: Interaction) -> None:
        assert isinstance(self.type.component, discord.ui.Select)
        host = self.host.value
        type = StatusQueryType(self.type.component.values[0])
        view = CreateStatusQueryView(self.status, self.callback, host, type)
        await interaction.response.edit_message(view=view)


class CreateStatusQueryView(LayoutView):
    container = discord.ui.Container()

    def __init__(
        self,
        status: Status,
        callback: _CreateCallback,
        host: str,
        type: StatusQueryType,
    ) -> None:
        super().__init__()
        self.status = status
        self.callback = callback
        self.host = host
        self.type = type

        content = [
            f"Type: {type.label}",
            f"Host: {host}",
        ]

        game_port, query_port = get_default_ports(type)
        query_port = query_port or "N/A"
        content.append(f"Game port: {game_port}")
        content.append(f"Query port: {query_port}")

        self.container.add_item(discord.ui.TextDisplay("## Create Status Query"))
        self.container.add_item(discord.ui.Separator())
        self.container.add_item(discord.ui.TextDisplay("\n".join(content)))
        self.container.add_item(CreateStatusQueryActionRow())


class CreateStatusQueryActionRow(discord.ui.ActionRow[CreateStatusQueryView]):
    def __init__(self) -> None:
        super().__init__()

    @discord.ui.button(label="Cancel", emoji="❌")
    async def cancel(self, interaction: Interaction, button: Button) -> None:
        interaction = cast("Interaction[Bot]", interaction)
        assert self.view is not None
        await self.view.callback(interaction, None)

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.success)
    async def create(self, interaction: Interaction, button: Button) -> None:
        assert self.view is not None
        modal = CreateStatusQueryModal(
            status=self.view.status,
            callback=self.view.callback,
            host=self.view.host,
            type=self.view.type,
        )
        await interaction.response.send_modal(modal)


class CreateStatusQueryModal(Modal, title="Create Status Query"):
    game_port = discord.ui.TextInput(
        label="Game Port",
        placeholder="The server's game port",
        min_length=1,
        max_length=5,
    )
    query_port = discord.ui.TextInput(
        label="Query Port",
        placeholder="The server's query port",
        min_length=1,
        max_length=5,
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
        *,
        status: Status,
        callback: _CreateCallback,
        host: str,
        type: StatusQueryType,
    ) -> None:
        super().__init__()
        self.status = status
        self.callback = callback
        self.host = host
        self.type = type

        game_port, query_port = get_default_ports(type)
        self.game_port.default = str(game_port)
        if query_port is not None:
            self.query_port.default = str(query_port)
        else:
            self.remove_item(self.query_port)

    async def on_submit(self, interaction: Interaction) -> None:
        interaction = cast("Interaction[Bot]", interaction)

        game_port = int(self.game_port.value)
        if self.type == StatusQueryType.ARMA_3:
            query_port = game_port + 1
        else:
            query_port = int(self.query_port.value or game_port)

        query = StatusQuery(
            status_query_id=0,
            status_id=self.status.status_id,
            host=self.host,
            game_port=game_port,
            query_port=query_port,
            type=self.type,
            priority=int(self.priority.value),
            enabled_at=interaction.created_at,
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
            format_enabled_at(query.enabled_at),
            f"**Host:** {query.host}",
            f"**Game port:** {query.game_port}",
            f"**Query port:** {query.query_port}",
            f"**Type:** {query.type.label}",
            f"**Priority:** {query.priority}",
            format_failed_at(query.failed_at),
        ]

        self.add_item(discord.ui.TextDisplay("\n".join(lines)))
        self.add_item(await _StatusQueryRow(self).render())

        return RenderArgs()


class _StatusQueryRow(discord.ui.ActionRow):
    def __init__(self, page: StatusQueryPage) -> None:
        super().__init__()
        self.page = page

    async def render(self) -> Self:
        self.clear_items()

        if self.page.query.enabled_at:
            self.add_item(self.disable)
        else:
            self.add_item(self.enable)

        self.add_item(self.delete)
        return self

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.primary, emoji="🔴")
    async def disable(self, interaction: Interaction, button: Button) -> None:
        enabled_at = None
        await self._set_enabled_at(enabled_at)
        self.page.query.enabled_at = enabled_at
        await self.page.book.edit(interaction)

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.primary, emoji="🟢")
    async def enable(self, interaction: Interaction, button: Button) -> None:
        enabled_at = utcnow()
        await self._set_enabled_at(enabled_at)
        self.page.query.enabled_at = enabled_at
        await self.page.book.edit(interaction)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete(self, interaction: Interaction, button: Button) -> None:
        async with connect() as conn:
            await conn.execute(
                "DELETE FROM status_query WHERE status_query_id = $1",
                self.page.query.status_query_id,
            )

        # HACK: we can't easily propagate deletion up, so let's just terminate the view.
        assert self.view is not None
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.view.stop()

    async def _set_enabled_at(self, enabled_at: datetime.datetime | None) -> None:
        async with connect() as conn:
            await conn.execute(
                "UPDATE status_query SET enabled_at = $1 WHERE status_query_id = $2",
                enabled_at,
                self.page.query.status_query_id,
            )
