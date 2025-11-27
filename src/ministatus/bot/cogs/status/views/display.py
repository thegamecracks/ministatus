from __future__ import annotations

import asyncio
import datetime
import logging
import math
import textwrap
import time
from io import BytesIO
from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator, Self, cast

import discord
from discord import Interaction, SelectOption
from discord.ui import Button, Select

from ministatus.bot.cogs.status.graph import create_player_count_graph
from ministatus.bot.cogs.status.permissions import check_channel_permissions
from ministatus.bot.db import connect_discord_database_client
from ministatus.bot.dt import past, utcnow
from ministatus.bot.views import LayoutView, Modal
from ministatus.db import (
    Status,
    StatusDisplay,
    StatusHistory,
    StatusHistoryPlayer,
    connect,
    connect_client,
)

from .book import Book, Page, RenderArgs, format_enabled_at, format_failed_at

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

    from .overview import StatusModify

DEFAULT_ATTACHMENTS_INTERVAL = 600

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
    graph_interval = discord.ui.Label(
        text="Graph Period",
        component=discord.ui.Select(
            options=[
                discord.SelectOption(label="1 hour", value=str(3600)),
                discord.SelectOption(label="2 hours", value=str(3600 * 2)),
                discord.SelectOption(label="6 hours", value=str(3600 * 6)),
                discord.SelectOption(label="12 hours", value=str(3600 * 12)),
                discord.SelectOption(label="24 hours", value=str(86400), default=True),
                discord.SelectOption(label="3 days", value=str(86400 * 3)),
                discord.SelectOption(label="7 days", value=str(86400 * 7)),
                discord.SelectOption(label="14 days", value=str(86400 * 14)),
                discord.SelectOption(label="30 days", value=str(86400 * 30)),
            ],
            placeholder="The graph's time period",
        ),
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
        assert isinstance(self.graph_interval.component, discord.ui.Select)

        channel = self.channel.component.values[0]
        channel = channel.resolve() or await channel.fetch()
        await check_channel_permissions(channel)

        accent_colour = discord.Color.from_str(self.accent_colour.value).value
        graph_colour = discord.Color.from_str(self.graph_colour.value).value

        assert not isinstance(channel, (discord.ForumChannel, discord.CategoryChannel))
        view = PlaceholderView(interaction.user, accent_colour=accent_colour)
        message = await channel.send(view=view)

        graph_interval = int(self.graph_interval.component.values[0])
        graph_interval = datetime.timedelta(seconds=graph_interval)

        display = StatusDisplay(
            message_id=message.id,
            status_id=self.status.status_id,
            accent_colour=accent_colour,
            graph_colour=graph_colour,
            graph_interval=graph_interval,
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
        content = [
            format_enabled_at(display.enabled_at),
            f"**Accent colour:** #{display.accent_colour:06X}",
            f"**Graph colour:** #{display.graph_colour:06X}",
            f"**Graph period:** {display.graph_interval}",
            format_failed_at(display.failed_at),
        ]
        self.add_item(discord.ui.TextDisplay("\n".join(content)))
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
        enabled_at = utcnow()
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

    def __init__(
        self,
        user: discord.Member | discord.User,
        *,
        accent_colour: int | None = None,
    ) -> None:
        super().__init__()
        self.container.accent_colour = accent_colour
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
    elif not history.down:
        return "Online 🟡"
    else:
        return "Offline 🔴"


class StatusDisplayView(LayoutView):
    container = discord.ui.Container()

    def __init__(self, bot: Bot, message_id: int, attachments_interval: float) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.message_id = message_id
        self.attachments_interval = attachments_interval

        self._last_attachment_refresh = -math.inf

    async def update(self) -> None:
        async with connect_discord_database_client(self.bot) as ddc:
            display = await ddc.client.get_status_display(message_id=self.message_id)
            if display is None:
                return log.warning(
                    "Ignoring update for status display #%d which does not exist",
                    self.message_id,
                )

            message = await ddc.get_message(message_id=self.message_id)
            assert message is not None

            status = await ddc.client.get_status(status_id=display.status_id)
            assert status is not None

            history = await ddc.client.get_status_history(
                status.status_id,
                after=past(display.graph_interval),
            )

        args = await self.render(status, display, history)
        await message.edit(view=self, **args.get_edit_kwargs())

    async def render(
        self,
        status: Status,
        display: StatusDisplay,
        history: list[StatusHistory],
    ) -> RenderArgs:
        self.clear_items()
        self.add_item(self.container)
        self.container.clear_items()
        self.container.accent_colour = display.accent_colour
        rendered = RenderArgs()

        if status.thumbnail:
            # Sections allow up to three text displays, and no other components
            thumbnail = discord.ui.Thumbnail("attachment://thumbnail.png")
            section = discord.ui.Section(accessory=thumbnail)
            self.container.add_item(section)
        else:
            section = self.container

        section.add_item(discord.ui.TextDisplay(f"## {status.display_name}"))
        if section == self.container:
            section.add_item(discord.ui.Separator())

        # Sometimes queries may fail at random, resulting in a one-off row
        # that's offline but not down. We want to exclude those rows so
        # our player list and graph appears stable, just in case it was an
        # intermittent failure.
        clean_history = [h for h in history if h.online or h.down]
        latest_raw = next(reversed(history), None)
        latest_known = next(reversed(clean_history), latest_raw)

        if latest_known is not None:
            players = (p for p in latest_known.players if p.name)
            players = sorted(players, key=lambda p: p.name.lower())
        else:
            players = []

        content = self._render_content(status, latest_raw, latest_known)
        section.add_item(discord.ui.TextDisplay("\n".join(content)))

        self.container.add_item(discord.ui.Separator())
        for item in self._render_players(players):
            self.container.add_item(item)

        self.container.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem("attachment://graph.png"),
            )
        )

        self._maybe_add_select(status)

        files = await self._maybe_refresh_attachments(status, display, clean_history)
        rendered.files.extend(files)
        return rendered

    def _render_content(
        self,
        status: Status,
        latest_raw: StatusHistory | None,
        latest_known: StatusHistory | None,
    ) -> list[str]:
        now = utcnow()
        last_updated = discord.utils.format_dt(now, "R")
        online = get_online_message(latest_raw)

        # TODO: tailor details to game
        content = [
            f"**Address:** {status.address}",
            f"**Status:** {online}",
            f"**Last updated:** {last_updated}",
        ]

        if status.game:
            content.append(f"**Game:** {status.game}")
        if status.map:
            content.append(f"**Map:** {status.map}")
        if status.version:
            content.append(f"**Version:** {status.version}")

        # TODO: add select option to list mods with possible URLs

        if latest_known is None:
            return content

        h = latest_known
        content.append(f"**Player count:** {h.num_players}/{h.max_players}")

        return content

    def _render_players(
        self,
        players: Iterable[StatusHistoryPlayer],
    ) -> Iterator[discord.ui.Item]:
        if not players:
            return

        lines = textwrap.wrap(", ".join([p.name for p in players]), 72)
        lines = lines[:40] + ["..."] * (len(lines) > 40)
        for chunk in discord.utils.as_chunks(lines, 3):
            content = "\n".join(chunk).removesuffix(",")
            content = discord.utils.escape_markdown(content, ignore_links=False)
            yield discord.ui.TextDisplay(content)

        yield discord.ui.Separator()

    def _maybe_add_select(self, status: Status) -> None:
        select = StatusDisplaySelect(status)
        if select.options:
            self.add_item(discord.ui.ActionRow(select))

    async def _maybe_refresh_attachments(
        self,
        status: Status,
        display: StatusDisplay,
        clean_history: list[StatusHistory],
    ) -> list[discord.File]:
        # NOTE: A status can have multiple displays, each of which independently
        #       generates its own images. Perhaps this should be shared?
        now = time.perf_counter()
        if now - self._last_attachment_refresh < self.attachments_interval:
            return []

        self._last_attachment_refresh = now
        files = []

        if status.thumbnail:
            f = discord.File(BytesIO(status.thumbnail), "thumbnail.png")
            files.append(f)

        graph = await asyncio.to_thread(
            create_player_count_graph,
            [(h.created_at, h.num_players) for h in clean_history],
            colour=display.graph_colour,
            max_players=max((h.max_players for h in clean_history), default=0),
        )
        f = discord.File(graph, "graph.png")
        files.append(f)

        return files


class StatusDisplaySelect(discord.ui.Select):
    def __init__(self, status: Status) -> None:
        super().__init__(
            options=self._make_options(status),
            placeholder="More details...",
        )
        self.status = status

    def _make_options(self, status: Status) -> list[SelectOption]:
        options: list[SelectOption] = []
        if status.mods:
            options.append(discord.SelectOption(label="Mods", emoji="🧩", value="mods"))
        return options

    async def callback(self, interaction: Interaction) -> None:
        interaction = cast("Interaction[Bot]", interaction)

        value = self.values[0]
        if value == "mods":
            return await self._send_mods(interaction)

    async def _send_mods(self, interaction: Interaction[Bot]) -> None:
        status = self.status
        view = discord.ui.LayoutView()

        if not status.mods:
            view.add_item(discord.ui.TextDisplay(f"{status.display_name} has no mods."))
            await interaction.response.send_message(ephemeral=True, view=view)
            return

        content = [f"Mods ({len(status.mods)}):"]
        mods = []
        for m in status.mods:
            name = discord.utils.escape_markdown(m.name)
            mods.append(f"[{name}]({m.url})" if m.url else name)
        mods = ", ".join(mods)
        content.append(mods)

        view.add_item(discord.ui.TextDisplay("\n".join(content)))
        await interaction.response.send_message(ephemeral=True, view=view)


async def update_display(bot: Bot, *, message_id: int) -> None:
    view = display_cache.get(message_id)
    if view is not None:
        return await view.update()

    log.debug("Creating view for display #%d", message_id)

    async with connect_client() as client:
        attachments_interval = await client.set_default_setting(
            "status-interval-attachments",
            DEFAULT_ATTACHMENTS_INTERVAL,
        )

    view = StatusDisplayView(bot, message_id, attachments_interval)
    await view.update()
    display_cache[message_id] = view
