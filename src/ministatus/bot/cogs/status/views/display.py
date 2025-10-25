from __future__ import annotations

import asyncio
import datetime
import logging
import math
import time
from typing import TYPE_CHECKING, Any, Callable, Self, cast

import discord
from discord import Interaction, SelectOption
from discord.ui import Button, Select

from ministatus.bot.cogs.status.graph import create_player_count_graph
from ministatus.bot.cogs.status.permissions import check_channel_permissions
from ministatus.bot.db import connect_discord_database_client
from ministatus.bot.views import LayoutView, Modal
from ministatus.db import (
    Status,
    StatusDisplay,
    StatusHistory,
    connect,
    fetch_status_by_id,
    fetch_status_display_by_id,
    fetch_status_history,
)

from .book import Book, Page, RenderArgs, get_enabled_text

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

    from .overview import StatusModify

DISPLAY_UPDATE_ATTACHMENTS_INTERVAL = 600

log = logging.getLogger(__name__)

display_cache: dict[int, StatusDisplayView] = {}


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
            modal = CreateStatusDisplayModal(self.page.status, self._create_callback)
            await interaction.response.send_modal(modal)
        else:
            display = discord.utils.get(
                self.page.status.displays, message_id=int(value)
            )
            assert display is not None
            self.page.book.push(StatusDisplayPage(self.page.book, display))
            await self.page.book.edit(interaction)

    async def _create_callback(
        self,
        interaction: Interaction[Bot],
        alert: StatusDisplay,
    ) -> None:
        self.page.book.push(StatusDisplayPage(self.page.book, alert))
        await self.page.book.edit(interaction)


class CreateStatusDisplayModal(Modal, title="Create Status Display"):
    channel = discord.ui.Label(
        text="Display Channel",
        component=discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            placeholder="The channel to send the display to",
        ),
    )
    accent_colour = discord.ui.TextInput(
        label="Accent Colour",
        default="#FFFFFF",
        placeholder="The accent colour of the display",
        min_length=7,
        max_length=7,
    )
    graph_colour = discord.ui.TextInput(
        label="Graph Colour",
        default="#FFFFFF",
        placeholder="The graph colour of the display",
        min_length=7,
        max_length=7,
    )

    def __init__(
        self,
        status: Status,
        callback: Callable[[Interaction[Bot], StatusDisplay], Any],
    ) -> None:
        super().__init__()
        self.status = status
        self.callback = callback

    async def on_submit(self, interaction: Interaction) -> None:
        interaction = cast("Interaction[Bot]", interaction)
        assert interaction.guild is not None
        assert isinstance(self.channel.component, discord.ui.ChannelSelect)

        channel = self.channel.component.values[0]
        channel = channel.resolve() or await channel.fetch()
        await check_channel_permissions(channel)

        assert not isinstance(channel, (discord.ForumChannel, discord.CategoryChannel))
        message = await channel.send(view=PlaceholderView(interaction.user))

        display = StatusDisplay(
            message_id=message.id,
            status_id=self.status.status_id,
            accent_colour=discord.Color.from_str(self.accent_colour.value).value,
            graph_colour=discord.Color.from_str(self.graph_colour.value).value,
            enabled_at=interaction.created_at,
        )

        async with connect_discord_database_client(interaction.client) as ddc:
            await ddc.add_message(message)
            display = await ddc.client.create_status_display(display)

        self.status.displays.append(display)
        await self.callback(interaction, display)


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
        interaction = cast("Interaction[Bot]", interaction)
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

        # Also try to clean up the display, if Discord permits us
        async with connect_discord_database_client(interaction.client) as ddc:
            message = await ddc.get_message(message_id=self.page.display.message_id)

        if message is not None:
            await message.delete(delay=0)

    async def _set_enabled_at(self, enabled_at: datetime.datetime | None) -> None:
        async with connect() as conn:
            await conn.execute(
                "UPDATE status_display SET enabled_at = $1 WHERE message_id = $2",
                enabled_at,
                self.page.display.message_id,
            )


class PlaceholderView(LayoutView):
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


def get_online_message(history: StatusHistory | None) -> str:
    if history is None:
        return "Unknown 🟡"
    elif history.online:
        return "Online 🟢"
    else:
        return "Offline 🔴"


class StatusDisplayView(LayoutView):
    container = discord.ui.Container()

    def __init__(self, bot: Bot, message_id: int) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.message_id = message_id

        self._last_attachment_refresh = -math.inf

    async def update(self) -> None:
        async with connect_discord_database_client(self.bot) as ddc:
            message = await ddc.get_message(message_id=self.message_id)

            if message is None:
                reason = f"Cannot retrieve message {self.message_id}"
                return await disable_display(self.message_id, reason)

            conn = ddc.client.conn
            display = await fetch_status_display_by_id(conn, message_id=self.message_id)
            assert display is not None

            status = await fetch_status_by_id(conn, status_id=display.status_id)
            assert status is not None

            history = await fetch_status_history(
                ddc.client.conn,
                status_ids=[status.status_id],
            )
            history = history.get(status.status_id, [])

        args = await self.render(status, display, history)
        await message.edit(view=self, **args.get_message_kwargs())

    async def render(
        self,
        status: Status,
        display: StatusDisplay,
        history: list[StatusHistory],
    ) -> RenderArgs:
        self.clear_items()
        self.container.clear_items()
        self.container.accent_colour = display.accent_colour

        rendered = RenderArgs()

        title = status.title or status.label
        title = discord.ui.TextDisplay(f"## {title}")

        if status.thumbnail:
            thumbnail = discord.ui.Thumbnail("attachment://thumbnail.png")
            frame = discord.ui.Section(accessory=thumbnail)
            frame.add_item(title)
            self.container.add_item(frame)
        else:
            self.container.add_item(title)

        self.container.add_item(discord.ui.Separator())

        latest = history[-1] if history else None
        online = get_online_message(latest)
        now = datetime.datetime.now(datetime.timezone.utc)
        last_updated = discord.utils.format_dt(now, "R")
        players = (
            sorted(latest.players, key=lambda p: p.name.lower())
            if latest is not None
            else []
        )
        max_players = latest and latest.max_players

        content = [
            f"**Address:** {status.address}",
            f"**Status:** {online}",
            f"**Last updated:** {last_updated}",
            f"**Player count:** {len(players)} / {max_players}",
            # TODO: tailor details to game
        ]

        self.container.add_item(discord.ui.TextDisplay("\n".join(content)))
        self.container.add_item(discord.ui.Separator())

        if players:
            content = []
            for chunk in discord.utils.as_chunks(players, 5):
                content.append(", ".join([p.name for p in chunk]))
            self.container.add_item(discord.ui.TextDisplay("\n".join(content)))
            self.container.add_item(discord.ui.Separator())

        self.container.add_item(discord.ui.File("attachment://graph.png"))

        self.add_item(self.container)

        files = await self._maybe_refresh_attachments(status, display, history)
        rendered.files.extend(files)

        return rendered

    async def _maybe_refresh_attachments(
        self,
        status: Status,
        display: StatusDisplay,
        history: list[StatusHistory],
    ) -> list[discord.File]:
        # NOTE: A status can have multiple displays, each of which independently
        #       generates its own images. Perhaps this should be shared?
        interval = DISPLAY_UPDATE_ATTACHMENTS_INTERVAL
        now = time.perf_counter()
        if now - self._last_attachment_refresh < interval:
            return []

        self._last_attachment_refresh = now
        files = []

        if status.thumbnail:
            f = discord.File(status.thumbnail, "thumbnail.png")
            files.append(f)

        graph = await asyncio.to_thread(
            create_player_count_graph,
            [(h.created_at, len(h.players)) for h in history],
            colour=display.graph_colour,
            max_players=max(h.max_players for h in history),
        )
        if graph is not None:
            f = discord.File(graph, "graph.png")
            files.append(f)

        return files


async def update_display(bot: Bot, *, message_id: int) -> None:
    view = display_cache.get(message_id)
    if view is not None:
        return await view.update()

    log.debug("Creating view for display #%d", message_id)
    view = StatusDisplayView(bot, message_id)
    await view.update()
    display_cache[message_id] = view


async def disable_display(message_id: int, reason: str) -> None:
    # TODO: store display failure reason in database
    log.warning("Status display #%d is invalid: %s", message_id, reason)
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_display SET enabled_at = NULL WHERE message_id = $1",
            message_id,
        )
