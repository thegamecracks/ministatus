from __future__ import annotations

import asyncio
import base64
import datetime
import json
import logging
import re
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Self, assert_never, cast

import aiohttp
import discord
from dns.asyncresolver import Resolver
from dns.exception import Timeout
from dns.rdatatype import A, AAAA, RdataType, SRV
from dns.rdtypes.IN.A import A as ARecord
from dns.rdtypes.IN.AAAA import AAAA as AAAARecord
from dns.rdtypes.IN.SRV import SRV as SRVRecord
from dns.resolver import Answer, Cache, NoAnswer, NoNameservers, NXDOMAIN, YXDOMAIN
from little_a2s import (
    Arma3Rules,
    AsyncA2S,
    ChallengeError,
    ClientEventInfo,
    PayloadError,
)
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ministatus.bot.dt import past, utcnow
from ministatus.db import (
    SQLiteConnection,
    Status,
    StatusDisplay,
    StatusMod,
    StatusQuery,
    StatusQueryType,
    connect,
    connect_client,
    status_mod_list_adapter,
)

from .alert import (
    disable_display,
    disable_query,
    send_alert_downtime_ended,
    send_alert_downtime_started,
)
from .views import update_display

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot

log = logging.getLogger(__name__)

DNS_TIMEOUT = 3
HISTORY_EXPIRES_AFTER = datetime.timedelta(days=30)
HISTORY_PLAYERS_EXPIRES_AFTER = datetime.timedelta(hours=1)
QUERY_DEAD_AFTER = datetime.timedelta(days=1)
QUERY_TIMEOUT = 3
HTTP_TIMEOUT = aiohttp.ClientTimeout(3)

FIVEM_COLOUR_CODE = re.compile(r"\^\d")

_resolver = Resolver()
_resolver.cache = Cache()


async def run_query_jobs(
    bot: Bot,
    *,
    max_concurrency: int,
) -> None:
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
        await _run_query_jobs(bot, statuses, max_concurrency=max_concurrency)
    except* (
        aiohttp.ServerDisconnectedError,  # sometimes raised by message.edit()
        discord.DiscordServerError,
        discord.RateLimited,
    ) as eg:
        # Ergh, drop all other exceptions so tasks.loop() can handle it
        e = eg.exceptions[0]
        log.warning("One or more status queries failed (%s)", type(e).__name__)
        raise e from None


async def _run_query_jobs(
    bot: Bot,
    statuses: list[Status],
    *,
    max_concurrency: int,
) -> None:
    tasks = []
    lock = asyncio.BoundedSemaphore(max_concurrency)
    async with QueryContext(bot) as ctx, asyncio.TaskGroup() as tg:
        for status in statuses:
            tasks.append(tg.create_task(query_status(ctx, status, lock)))

            # Let all tasks run first, and collect any errors to raise afterwards
        await asyncio.wait(tasks)

    exceptions = [e for t in tasks if (e := t.exception()) is not None]
    if exceptions:
        raise ExceptionGroup(f"{len(exceptions)} query job(s) failed", exceptions)


async def query_status(
    ctx: QueryContext,
    status: Status,
    lock: asyncio.Semaphore,
) -> None:
    if not status.queries:
        return

    async with lock:
        for query in status.queries:
            info = await maybe_query(ctx, status, query)
            if info is not None:
                await record_info(ctx, status, info)
                break
        else:
            await record_offline(ctx, status)

        for display in status.displays:
            await maybe_update_display(ctx.bot, status, display)


async def maybe_query(
    ctx: QueryContext,
    status: Status,
    query: StatusQuery,
) -> Info | None:
    try:
        info = await send_query(ctx, query)
    except FailedQueryError as e:
        log.debug("Query #%d failed: %s", query.status_query_id, e, exc_info=e)
        if await set_query_failed(query):
            reason = "Offline for extended period of time"
            return await disable_query(ctx.bot, status, query, reason)
    except InvalidQueryError as e:
        await set_query_failed(query)
        return await disable_query(ctx.bot, status, query, str(e))
    except Exception:
        await set_query_failed(query)
        raise
    else:
        await set_query_success(query)
        return info


async def send_query(ctx: QueryContext, query: StatusQuery) -> Info | None:
    if query.type == StatusQueryType.ARMA_3:
        return await query_source(ctx, query)
    elif query.type == StatusQueryType.ARMA_REFORGER:
        return await query_source(ctx, query)
    elif query.type == StatusQueryType.FIVEM:
        return await query_fivem(ctx.bot.session, query)
    elif query.type == StatusQueryType.MINECRAFT_BEDROCK:
        return await query_minecraft_bedrock(query)
    elif query.type == StatusQueryType.MINECRAFT_JAVA:
        return await query_minecraft_java(query)
    elif query.type == StatusQueryType.SOURCE:
        return await query_source(ctx, query)
    elif query.type == StatusQueryType.TEAMSPEAK_3:
        return await query_teamspeak_3(query)
    elif query.type == StatusQueryType.PROJECT_ZOMBOID:
        return await query_source(ctx, query)
    else:
        assert_never(query.type)


async def query_fivem(session: aiohttp.ClientSession, query: StatusQuery) -> Info:
    async def get(filename: str) -> Any:
        params = {"v": int(now.timestamp())}
        url = f"https://{host}:{port}/{filename}"
        # NOTE: several servers use self-signed certificates, so ssl=False is needed
        return await _http_get_json(session, url, params=params, ssl=False)

    host, port = await resolve_host(query)
    now = utcnow()

    dynamic = await get("dynamic.json")
    info = await get("info.json")
    players = await get("players.json")

    try:
        dynamic = FiveMDynamic.model_validate(dynamic)
        info = FiveMInfo.model_validate(info)
        players = fivem_players_list_adapter.validate_python(players)
    except ValidationError as e:
        message = "Unexpected response format; did server shutdown?"
        raise FailedQueryError(message) from e

    vars = info.vars
    thumbnail = base64.b64decode(info.icon) if info.icon else None

    title = dynamic.hostname or vars.sv_projectName or ""
    title = FIVEM_COLOUR_CODE.sub("", title).strip()
    version = dynamic.iv or info.version
    players = [Player(name=p.name) for p in players if p.name]

    return Info(
        title=title or None,
        address=query.address,
        thumbnail=thumbnail,
        max_players=dynamic.sv_maxclients or vars.sv_maxClients,
        num_players=dynamic.clients,
        game=dynamic.gametype or None,
        map=dynamic.mapname or None,
        mods=None,  # mods=info.get("resources", []),
        version=str(version) if version else None,
        players=players,
    )


async def query_minecraft_bedrock(query: StatusQuery) -> Info:
    from opengsq import RakNet

    host, port = await resolve_host(query)
    proto = RakNet(host, port, QUERY_TIMEOUT)

    try:
        status = await proto.get_status()
    except TimeoutError as e:
        raise FailedQueryError("Query timed out") from e

    return Info(
        title=status.motd_line1 or None,
        address=query.address,
        thumbnail=None,
        max_players=status.max_players,
        num_players=status.num_players,
        game=status.game_mode,
        map=None,
        mods=None,
        version=status.version_name,
        players=[],
    )


async def query_minecraft_java(query: StatusQuery) -> Info:
    # https://minecraft.wiki/w/Java_Edition_protocol/Server_List_Ping
    from opengsq import Minecraft

    host, port = await resolve_host(query)
    proto = Minecraft(host, port, QUERY_TIMEOUT)

    try:
        status = await proto.get_status()
    except OSError as e:
        raise FailedQueryError("Query timed out") from e

    favicon = cast(str, status.get("favicon", ""))
    if favicon.startswith("data:image/png;base64,"):
        favicon = favicon.removeprefix("data:image/png;base64,")
        thumbnail = base64.decodebytes(favicon.encode())
    else:
        thumbnail = None

    if players := status.get("players"):
        max_players = players.get("max", 0)
        num_players = players.get("online", 0)
        sample = [
            Player(name=name)
            for p in players.get("sample", [])
            if p.get("id", "") not in ("", "00000000-0000-0000-0000-000000000000")
            and (name := p.get("name"))
        ]
    else:
        max_players = 0
        num_players = 0
        sample = []

    return Info(
        title=None,  # TODO: parse MOTD for title
        address=query.address,
        thumbnail=thumbnail,
        max_players=max_players,
        num_players=num_players,
        game=None,
        map=None,
        mods=None,  # TODO: parse "modinfo" key?
        version=status["version"]["name"],  # can be a long string for proxy servers
        players=sample,
    )


async def query_source(ctx: QueryContext, query: StatusQuery) -> Info:
    host, port = await resolve_host(query)
    proto = await ctx.start_source(host)

    try:
        async with asyncio.timeout(QUERY_TIMEOUT):
            info = await proto.info((host, port))
            players = await proto.players((host, port))
            rules = await SourceRules.maybe_query(proto, host, port, info)
    except ChallengeError as e:
        raise InvalidQueryError("Server responded with too many challenges") from e
    except PayloadError as e:
        raise FailedQueryError("Query response was malformed") from e
    except TimeoutError as e:
        raise FailedQueryError("Query timed out") from e

    players = [Player(name=p.name) for p in players]

    return Info(
        title=info.name,
        address=query.address,
        thumbnail=None,
        max_players=info.max_players,
        num_players=info.players,
        game=info.game,
        map=info.map,
        mods=rules and rules.mods,
        version=info.version,
        players=players,
    )


async def query_teamspeak_3(query: StatusQuery) -> Info:
    from opengsq import TeamSpeak3

    # In this context, "game port" is the TeamSpeak query port and "query port"
    # is the TeamSpeak voice port. SRV records are looked up for the voice port.
    query_port = query.game_port or 10011
    host, voice_port = await resolve_host(query)
    proto = TeamSpeak3(host, query_port, voice_port, QUERY_TIMEOUT)

    try:
        info = await proto.get_info()
        clients = await proto.get_clients()
    except TimeoutError as e:
        raise FailedQueryError("Query timed out") from e

    clients = [
        Player(name=name)
        for c in clients
        if c.get("client_type") == "0" and (name := c.get("client_nickname"))
    ]

    return Info(
        title=info.get("virtualserver_name", "").strip() or None,
        address=f"{query.host}:{query.query_port}" if query.query_port else query.host,
        thumbnail=None,
        max_players=int(info.get("virtualserver_maxclients") or 0),
        num_players=int(info.get("virtualserver_clientsonline") or 0),
        game=None,
        map=None,
        mods=None,
        version=info.get("virtualserver_version", "").strip() or None,
        players=clients,
    )


async def _http_get_json(session: aiohttp.ClientSession, *args, **kwargs) -> Any:
    kwargs.setdefault("timeout", HTTP_TIMEOUT)
    try:
        async with session.get(*args, **kwargs) as res:
            res.raise_for_status()
            return await res.json(content_type=None)
    except TimeoutError as e:
        raise FailedQueryError("HTTP request timed out") from e
    except aiohttp.ClientConnectorError as e:
        raise FailedQueryError("Failed to connect to server") from e
    except aiohttp.ClientResponseError as e:
        message = f"Server responded with {e.status}"
        if 400 <= e.status < 500:  # Maybe support 429 ratelimiting?
            raise InvalidQueryError(message) from e
        raise FailedQueryError(message) from e
    except json.JSONDecodeError as e:
        raise InvalidQueryError("Server responded with malformed JSON") from e


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
    ipv6_allowed = True  # TODO: check which games work over IPv6
    if type == StatusQueryType.ARMA_3:
        host_srv = f"_arma3._udp.{host}"
        srv_offset = 1
    elif type == StatusQueryType.FIVEM:
        host_srv = f"_cfx._udp.{host}"
    elif type == StatusQueryType.MINECRAFT_JAVA:
        host_srv = f"_minecraft._tcp.{host}"
    elif type == StatusQueryType.TEAMSPEAK_3:
        host_srv = f"_ts3._udp.{host}"

    # See also https://github.com/py-mine/mcstatus/blob/v12.0.6/mcstatus/dns.py
    # NOTE: there could be multiple DNS records, but we're always returning the first

    if host_srv and (answers := await _resolve(host_srv, SRV)):
        record = cast(SRVRecord, answers[0])
        log.debug("Resolved query #%d with SRV record", query.status_query_id)
        host = str(record.target).rstrip(".")
        query_port = record.port + srv_offset

    if host_srv and query_port < 1:
        raise InvalidQueryError("Query port not defined and no SRV DNS record found")
    elif query_port < 1:
        raise InvalidQueryError("Domain name provided without a query port")

    if answers := await _resolve(host, A):
        record = cast(ARecord, answers[0])
        log.debug("Resolved query #%d with A record", query.status_query_id)
        return str(record.address), query_port

    if ipv6_allowed and (answers := await _resolve(host, AAAA)):
        record = cast(AAAARecord, answers[0])
        log.debug("Resolved query #%d with AAAA record", query.status_query_id)
        return str(record.address), query_port

    raise InvalidQueryError("DNS name does not exist")


async def _resolve(qname: str, rdtype: RdataType) -> Answer | None:
    try:
        return await _resolver.resolve(qname, rdtype, lifetime=DNS_TIMEOUT)
    except Timeout as e:
        log.warning("DNS lookup timed out after %.2fs", DNS_TIMEOUT)
        raise FailedQueryError("DNS lookup timed out") from e
    except (NoAnswer, NXDOMAIN):
        return None
    except NoNameservers as e:
        log.warning("DNS nameservers unavailable")
        raise FailedQueryError("DNS nameservers unavailable") from e
    except YXDOMAIN as e:
        raise InvalidQueryError("DNS name is too long") from e


async def set_query_failed(query: StatusQuery) -> bool:
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


async def record_offline(ctx: QueryContext, status: Status) -> None:
    log.debug("Recording status #%d as offline", status.status_id)
    await prune_history(status)

    # Use transaction="write" to eagerly lock the database with a timeout,
    # since our transaction starts with a read.
    async with connect(transaction="write") as conn:
        downtime = await _check_downtime(conn, status)
        await conn.execute(
            "INSERT INTO status_history (created_at, status_id, online, down) "
            "VALUES ($1, $2, $3, $4) RETURNING status_history_id",
            utcnow(),
            status.status_id,
            False,
            downtime in (DowntimeStatus.DOWNTIME, DowntimeStatus.PENDING_DOWNTIME),
        )

    if downtime == DowntimeStatus.PENDING_DOWNTIME:
        await send_alert_downtime_started(ctx.bot, status)


async def record_info(ctx: QueryContext, status: Status, info: Info) -> None:
    log.debug("Recording status #%d as online", status.status_id)

    mods = None
    if info.mods is not None:
        mods = status_mod_list_adapter.dump_json(info.mods).decode()

    await prune_history(status)
    async with connect() as conn:
        await conn.execute(
            "UPDATE status SET "
            "title     = COALESCE($1, title), "
            "address   = COALESCE($2, address), "
            "thumbnail = COALESCE($3, thumbnail), "
            "game      = COALESCE($4, game), "
            "map       = COALESCE($5, map), "
            "mods      = COALESCE($6, mods), "
            "version   = COALESCE($7, version) "
            "WHERE status_id =    $8",
            info.title,
            info.address,
            info.thumbnail,
            info.game,
            info.map,
            mods,
            info.version,
            status.status_id,
        )

        downtime = await _check_downtime(conn, status)
        status_history_id = await conn.fetchval(
            "INSERT INTO status_history "
            "(created_at, status_id, online, max_players, num_players, down) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING status_history_id",
            utcnow(),
            status.status_id,
            True,
            info.max_players,
            info.num_players,
            False,  # a successful query always terminates downtime
        )

        await conn.executemany(
            "INSERT INTO status_history_player (status_history_id, name) "
            "VALUES ($1, $2)",
            ((status_history_id, player.name) for player in info.players),
        )

    if downtime == DowntimeStatus.DOWNTIME:
        await send_alert_downtime_ended(ctx.bot, status)


async def prune_history(status: Status) -> None:
    # FIXME: should prune periodically instead of on every insert
    async with connect() as conn:
        await conn.execute(
            "DELETE FROM status_history WHERE status_id = $1 AND created_at < $2",
            status.status_id,
            past(HISTORY_EXPIRES_AFTER),
        )
        await conn.execute(
            "DELETE FROM status_history_player WHERE status_history_player_id IN "
            "(SELECT status_history_player_id FROM status_history_player "
            "JOIN status_history USING (status_history_id) "
            "WHERE status_id = $1 AND created_at < $2)",
            status.status_id,
            past(HISTORY_PLAYERS_EXPIRES_AFTER),
        )


async def _check_downtime(conn: SQLiteConnection, status: Status) -> DowntimeStatus:
    # The idea is if we have three consecutive offline queries, we should
    # consider the server as down, and the server is otherwise online if
    # at least one of the recent queries was successful.
    #
    # Since this function is called before a new row is inserted,
    # we'll only select the last two rows and let the caller decide
    # for the next row if it's uptime or downtime.
    #
    # NOTE: downtime is directly affected by query interval
    history = await conn.fetch(
        "SELECT online, down FROM status_history WHERE status_id = $1 "
        "ORDER BY status_history_id DESC LIMIT 2",
        status.status_id,
    )

    if any(row["online"] for row in history):
        return DowntimeStatus.ONLINE
    elif any(row["down"] for row in history):
        return DowntimeStatus.DOWNTIME
    else:
        # This case also applies to fresh statuses without any history
        return DowntimeStatus.PENDING_DOWNTIME


async def maybe_update_display(
    bot: Bot,
    status: Status,
    display: StatusDisplay,
) -> None:
    try:
        await update_display(bot, message_id=display.message_id)
    except (discord.Forbidden, discord.NotFound) as e:
        await set_display_failed(display)
        reason = str(e)
        await disable_display(bot, status, display, reason)
    except Exception:
        await set_display_failed(display)
        raise
    else:
        await set_display_success(display)


async def set_display_failed(display: StatusDisplay) -> None:
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


class QueryContext:
    _a2s_ipv4: AsyncA2S | None = None
    _a2s_ipv6: AsyncA2S | None = None

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._stack.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, tb) -> None:
        await self._stack.__aexit__(exc_type, exc_val, tb)

    async def start_source(self, host: str) -> AsyncA2S:
        if ":" in host:
            return await self._start_source_ipv6()
        return await self._start_source_ipv4()

    async def _start_source_ipv4(self) -> AsyncA2S:
        if self._a2s_ipv4 is not None:
            return self._a2s_ipv4

        self._a2s_ipv4 = AsyncA2S.from_ipv4()
        await self._stack.enter_async_context(self._a2s_ipv4)
        return self._a2s_ipv4

    async def _start_source_ipv6(self) -> AsyncA2S:
        if self._a2s_ipv6 is not None:
            return self._a2s_ipv6

        self._a2s_ipv6 = AsyncA2S.from_ipv6()
        await self._stack.enter_async_context(self._a2s_ipv6)
        return self._a2s_ipv6


@dataclass(kw_only=True)
class SourceRules:
    mods: list[StatusMod]

    @classmethod
    async def maybe_query(
        cls,
        proto: AsyncA2S,
        host: str,
        port: int,
        info: ClientEventInfo,
    ) -> Self | None:
        folder = info.folder.lower()
        if folder in ("arma3", "dayz"):
            rules = await proto.rules((host, port))

            try:
                rules = Arma3Rules.from_rules(rules)
            except (EOFError, ValueError) as e:
                raise FailedQueryError("Rules response was malformed") from e

            return cls.from_arma3_rules(rules)

    @classmethod
    def from_arma3_rules(cls, rules: Arma3Rules) -> Self:
        mods: list[StatusMod] = []
        for m in rules.mods:
            if m.dlc:
                name = m.name or f"Creator DLC ({m.steam_id})"
                url = "https://store.steampowered.com/app/"
            else:
                name = m.name
                url = "https://steamcommunity.com/sharedfiles/filedetails/?id="

            # Some mods return steam ID of 0, don't include URLs for them
            url = f"{url}{m.steam_id}" if m.steam_id else None
            mod = StatusMod(name=name, url=url)
            mods.append(mod)

        return cls(mods=mods)


@dataclass(kw_only=True)
class Info:
    title: str | None
    address: str
    thumbnail: bytes | None
    game: str | None
    map: str | None
    mods: list[StatusMod] | None
    version: str | None

    max_players: int
    num_players: int
    players: list[Player]


@dataclass(kw_only=True)
class Player:
    name: str


# https://github.com/citizenfx/fivem/blob/v1.0.0.21703/code/components/citizen-server-impl/src/InfoHttpHandler.cpp#L562-L576
# Tolerate missing keys for everything, just in case...
class FiveMDynamic(BaseModel):
    hostname: str = ""
    gametype: str = ""
    mapname: str = ""
    clients: int = 0
    iv: int = 0
    sv_maxclients: int = 0


class FiveMInfoVars(BaseModel):
    gamename: str = ""
    sv_maxClients: int = 0
    sv_projectDesc: str = ""
    sv_projectName: str = ""
    tags: str = ""


class FiveMInfo(BaseModel):
    icon: str | None = None
    resources: list[str] = Field(default_factory=list)
    server: str = ""
    vars: FiveMInfoVars = Field(default_factory=FiveMInfoVars)
    version: int = 0


class FiveMPlayer(BaseModel):
    name: str


fivem_players_list_adapter = TypeAdapter(list[FiveMPlayer])


class DowntimeStatus(Enum):
    ONLINE = 1
    """The server was recently online."""
    PENDING_DOWNTIME = 2
    """The server is down, but has not yet been logged as downtime."""
    DOWNTIME = 3
    """The server is down and has been logged as downtime."""


class QueryError(RuntimeError):
    """An error occurred while querying a server."""


class FailedQueryError(QueryError):
    """The query method could not successfully reach the server."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class InvalidQueryError(QueryError):
    """The query method is invalid and should be disabled."""
