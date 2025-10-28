from __future__ import annotations

import asyncio
import base64
import datetime
import logging
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never, cast

import discord
from dns.asyncresolver import Resolver
from dns.exception import Timeout
from dns.rdatatype import A, AAAA, RdataType, SRV
from dns.rdtypes.IN.A import A as ARecord
from dns.rdtypes.IN.AAAA import AAAA as AAAARecord
from dns.rdtypes.IN.SRV import SRV as SRVRecord
from dns.resolver import Answer, Cache, NoAnswer, NoNameservers, NXDOMAIN, YXDOMAIN

from ministatus.bot.dt import past, utcnow
from ministatus.db import (
    Status,
    StatusDisplay,
    StatusQuery,
    StatusQueryType,
    connect,
    connect_client,
)

from .alert import disable_display, disable_query
from .views import update_display

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

log = logging.getLogger(__name__)

DNS_TIMEOUT = 3
HISTORY_EXPIRES_AFTER = datetime.timedelta(days=1)  # TODO: customize history window
QUERY_DEAD_AFTER = datetime.timedelta(days=7)
QUERY_TIMEOUT = 3

_resolver = Resolver()
_resolver.cache = Cache()


async def run_query_jobs(bot: Bot) -> None:
    guild_ids = [guild.id for guild in bot.guilds]

    async with connect_client() as client:
        statuses = await client.get_bulk_statuses_by_guilds(
            *guild_ids,
            only_enabled=True,
            with_relationships=True,
        )

    if not statuses:
        return

    try:
        tasks = []
        async with asyncio.TaskGroup() as tg:
            for status in statuses:
                tasks.append(tg.create_task(query_status(bot, status)))

            # Let all tasks run first, and collect any errors to raise afterwards
            await asyncio.wait(tasks)

        exceptions = [e for t in tasks if (e := t.exception()) is not None]
        if exceptions:
            raise ExceptionGroup(f"{len(exceptions)} query job(s) failed", exceptions)

    except* (discord.DiscordServerError, discord.RateLimited) as eg:
        # Ergh, drop all other exceptions so tasks.loop() can handle it
        log.warning("One or more status queries failed: %s", exc_info=eg)
        e = eg.exceptions[0]
        raise e from None


async def query_status(bot: Bot, status: Status) -> None:
    if not status.queries:
        return

    for query in status.queries:
        info = await maybe_query(bot, query)
        if info is not None:
            await record_info(status, info)
            break
    else:
        await record_offline(status)

    for display in status.displays:
        await maybe_update_display(bot, display)


async def maybe_query(bot: Bot, query: StatusQuery) -> Info | None:
    try:
        info = await send_query(query)
    except FailedQueryError as e:
        log.debug("Query #%d failed: %s", query.status_query_id, e)
        expired = await set_query_failed(query)
        if not expired:
            return
        reason = "Offline for extended period of time"
        return await disable_query(bot, query, reason)
    except InvalidQueryError as e:
        await set_query_failed(query)
        return await disable_query(bot, query, str(e))
    else:
        await set_query_success(query)
        return info


async def send_query(query: StatusQuery) -> Info | None:
    if query.type == StatusQueryType.ARMA_3:
        return await query_source(query)
    elif query.type == StatusQueryType.ARMA_REFORGER:
        return await query_source(query)
    # NOTE: Bedrock uses the RakNet protocol, but opengsq's implementation
    #       seems to be broken. Use mcstatus instead, or wait for a hotfix.
    # elif query.type == StatusQueryType.MINECRAFT_BEDROCK:
    #     return await query_minecraft_bedrock(query)
    elif query.type == StatusQueryType.MINECRAFT_JAVA:
        return await query_minecraft_java(query)
    elif query.type == StatusQueryType.SOURCE:
        return await query_source(query)
    elif query.type == StatusQueryType.PROJECT_ZOMBOID:
        return await query_source(query)  # Wait, it's all source? Always has been
    else:
        assert_never(query.type)


async def query_minecraft_java(query: StatusQuery) -> Info:
    from opengsq import Minecraft

    host, port = await resolve_host(query)
    proto = Minecraft(host, port, QUERY_TIMEOUT)

    try:
        status = await proto.get_status()
    except TimeoutError as e:
        raise FailedQueryError("Query timed out") from e

    favicon = cast(str, status.get("favicon", ""))
    if favicon.startswith("data:image/png;base64,"):
        favicon = favicon.removeprefix("data:image/png;base64,")
        thumbnail = base64.decodebytes(favicon.encode())
    else:
        thumbnail = None

    return Info(
        title=None,  # TODO: parse MOTD for title
        address=_format_address(query),
        thumbnail=thumbnail,
        max_players=status["players"]["max"],
        num_players=status["players"]["online"],
        players=[],
    )


async def query_source(query: StatusQuery) -> Info:
    from opengsq import Source

    host, port = await resolve_host(query)
    proto = Source(host, port, QUERY_TIMEOUT)

    try:
        info = await proto.get_info()
        players = await proto.get_players()
        # rules = await proto.get_rules()
    except TimeoutError as e:
        raise FailedQueryError("Query timed out") from e

    players = [Player(name=p.name) for p in players]

    return Info(
        title=info.name,
        address=_format_address(query),
        thumbnail=None,
        max_players=info.max_players,
        num_players=len(players),
        players=players,
    )


def _format_address(query: StatusQuery) -> str:
    if query.game_port:
        return f"{query.host}:{query.game_port}"
    elif query.query_port:
        return f"{query.host}:{query.query_port}"
    return query.host


async def resolve_host(query: StatusQuery) -> tuple[str, int]:
    from ipaddress import IPv4Address, IPv6Address

    host = query.host
    query_port = query.query_port
    type = query.type

    ip = None
    with suppress(ValueError):
        ip = IPv4Address(host)

    if ip is None:
        with suppress(ValueError):
            ip = IPv6Address(host)

    if ip is not None and query_port < 1:
        raise InvalidQueryError("IP address was provided without a query port")
    elif ip is not None:
        return host, query_port

    host_srv = None
    srv_offset = 0
    ipv6_allowed = False  # TODO: check which games work over IPv6
    if type == StatusQueryType.ARMA_3:
        host_srv = f"_arma3._udp.{host}"
        srv_offset = 1
    elif type == StatusQueryType.MINECRAFT_JAVA:
        host_srv = f"_minecraft._tcp.{host}"

    # See also https://github.com/py-mine/mcstatus/blob/v12.0.6/mcstatus/dns.py
    # NOTE: there could be multiple DNS records, but we're always returning the first

    if host_srv and (answers := await _resolve(host_srv, SRV)):
        # FIXME: how long are no answers cached for SRV queries?
        record = cast(SRVRecord, answers[0])
        log.debug("Resolved query #%d with SRV record", query.status_query_id)
        host = str(record.target).rstrip(".")
        query_port = record.port + srv_offset

    if host_srv and query_port < 1:
        raise InvalidQueryError("Query port not defined and no SRV DNS record found")
    elif query_port < 1:
        raise InvalidQueryError("Domain name provided without a query port")

    if ipv6_allowed and (answers := await _resolve(host, AAAA)):
        record = cast(AAAARecord, answers[0])
        log.debug("Resolved query #%d with AAAA record", query.status_query_id)
        return str(record.address), query_port

    if answers := await _resolve(host, A):
        record = cast(ARecord, answers[0])
        log.debug("Resolved query #%d with A record", query.status_query_id)
        return str(record.address), query_port

    raise InvalidQueryError("DNS name does not exist")


async def _resolve(qname: str, rdtype: RdataType) -> Answer | None:
    try:
        return await _resolver.resolve(qname, rdtype, lifetime=DNS_TIMEOUT)
    except Timeout:
        log.warning("DNS lookup for query #{query.id}timed out after %.2fs")
        raise
    except (NoAnswer, NXDOMAIN):
        return None
    except NoNameservers:
        log.exception("Nameservers unavailable")
        raise
    except YXDOMAIN as e:
        raise InvalidQueryError("DNS name is too long") from e


async def set_query_failed(query: StatusQuery) -> bool:
    # TODO: send alerts
    now = utcnow()
    async with connect() as conn:
        failed_at = await conn.fetchval(
            "UPDATE status_query SET failed_at = COALESCE(failed_at, $1) "
            "WHERE status_query_id = $2 RETURNING failed_at",
            now,
            query.status_query_id,
        )
        assert isinstance(failed_at, datetime.datetime)
        return now - failed_at > QUERY_DEAD_AFTER


async def set_query_success(query: StatusQuery) -> None:
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_query SET failed_at = NULL WHERE status_query_id = $1",
            query.status_query_id,
        )


async def record_offline(status: Status) -> None:
    log.debug("Recording status #%d as offline", status.status_id)
    await prune_history(status)
    async with connect() as conn:
        await conn.execute(
            "INSERT INTO status_history (created_at, status_id, online) "
            "VALUES ($1, $2, $3) RETURNING status_history_id",
            utcnow(),
            status.status_id,
            False,
        )


async def record_info(status: Status, info: Info) -> None:
    log.debug("Recording status #%d as online", status.status_id)
    await prune_history(status)
    async with connect() as conn:
        await conn.execute(
            "UPDATE status SET title = COALESCE($1, title), "
            "address = COALESCE($2, address), thumbnail = COALESCE($3, thumbnail) "
            "WHERE status_id = $4",
            info.title,
            info.address,
            info.thumbnail,
            status.status_id,
        )

        status_history_id = await conn.fetchval(
            "INSERT INTO status_history "
            "(created_at, status_id, online, max_players, num_players) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING status_history_id",
            utcnow(),
            status.status_id,
            True,
            info.max_players,
            info.num_players,
        )

        await conn.executemany(
            "INSERT INTO status_history_player (status_history_id, name) "
            "VALUES ($1, $2)",
            ((status_history_id, player.name) for player in info.players),
        )


async def prune_history(status: Status) -> None:
    # FIXME: should prune periodically instead of on every insert
    async with connect() as conn:
        await conn.execute(
            "DELETE FROM status_history WHERE status_id = $1 AND created_at < $2",
            status.status_id,
            past(HISTORY_EXPIRES_AFTER),
        )


async def maybe_update_display(bot: Bot, display: StatusDisplay) -> None:
    try:
        await update_display(bot, message_id=display.message_id)
    except (discord.Forbidden, discord.NotFound) as e:
        await set_display_failed(display)
        reason = str(e)
        await disable_display(bot, display, reason)
    except Exception:
        await set_display_failed(display)
        raise
    else:
        await set_display_success(display)


async def set_display_failed(display: StatusDisplay) -> None:
    # TODO: send alerts
    now = utcnow()
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_display SET failed_at = COALESCE(failed_at, $1) "
            "WHERE message_id = $2 RETURNING failed_at",
            now,
            display.message_id,
        )


async def set_display_success(display: StatusDisplay) -> None:
    async with connect() as conn:
        await conn.execute(
            "UPDATE status_display SET failed_at = NULL WHERE message_id = $1",
            display.message_id,
        )


@dataclass(kw_only=True)
class Info:
    title: str | None
    address: str
    thumbnail: bytes | None

    max_players: int
    num_players: int
    players: list[Player]


@dataclass(kw_only=True)
class Player:
    name: str


class QueryError(RuntimeError):
    """An error occurred while querying a server."""


class FailedQueryError(QueryError):
    """The query method could not successfully reach the server."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class InvalidQueryError(QueryError):
    """The query method is invalid and should be disabled."""
