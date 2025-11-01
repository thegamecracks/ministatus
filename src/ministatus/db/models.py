from __future__ import annotations

import datetime
from contextlib import suppress
from enum import StrEnum
from typing import Annotated, assert_never

from pydantic import AfterValidator, BaseModel, Field


def is_snowflake(value: int) -> int:
    DISCORD_EPOCH = 1420070400000

    timestamp = ((value >> 22) + DISCORD_EPOCH) / 1000
    try:
        datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    except (OSError, OverflowError) as e:
        raise ValueError("Invalid Discord snowflake value") from e

    return value


def parse_host(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("value cannot be empty")

    from ipaddress import IPv4Address, IPv6Address

    with suppress(ValueError):
        return IPv4Address(value) and value

    with suppress(ValueError):
        return IPv6Address(value) and value

    from dns.name import from_text

    with suppress(ValueError):
        name = from_text(value)
        if len(name.labels) < 3:
            raise ValueError("value cannot be a top-level domain only")
        elif name.labels[-2].decode().isdecimal():  # Incomplete IP address?
            raise ValueError("top-level domain cannot be a number")

        return name.to_text(omit_final_dot=True)

    raise ValueError("value is not a valid IP address or domain name")


Color = Annotated[int, Field(ge=0, le=0xFFFFFF)]
Host = Annotated[str, AfterValidator(parse_host)]
Snowflake = Annotated[int, AfterValidator(is_snowflake)]


class DiscordUser(BaseModel):
    guild_id: Snowflake


class DiscordGuild(BaseModel):
    guild_id: Snowflake


class DiscordChannel(BaseModel):
    channel_id: Snowflake
    guild_id: Snowflake | None = Field(default=None)


class DiscordMessage(BaseModel):
    message_id: Snowflake
    channel_id: Snowflake


class DiscordMember(BaseModel):
    guild_id: Snowflake
    user_id: Snowflake


class Status(BaseModel):
    status_id: int
    guild_id: Snowflake
    label: str

    title: str | None = Field(default=None)
    address: str | None = Field(default=None)
    thumbnail: bytes | None = Field(default=None)
    enabled_at: datetime.datetime | None = Field(default=None)
    failed_at: datetime.datetime | None = Field(default=None)
    game: str | None = Field(default=None)
    map: str | None = Field(default=None)
    mods: str | None = Field(default=None)
    version: str | None = Field(default=None)

    alerts: list[StatusAlert] = Field(default_factory=list)
    displays: list[StatusDisplay] = Field(default_factory=list)
    queries: list[StatusQuery] = Field(default_factory=list)


class StatusAlert(BaseModel):
    status_alert_id: int
    status_id: int
    channel_id: Snowflake
    enabled_at: datetime.datetime | None = Field(default=None)
    failed_at: datetime.datetime | None = Field(default=None)
    send_audit: bool = Field(default=False)
    send_downtime: bool = Field(default=False)


class StatusDisplay(BaseModel):
    message_id: Snowflake
    status_id: int

    enabled_at: datetime.datetime | None = Field(default=None)
    failed_at: datetime.datetime | None = Field(default=None)
    accent_colour: Color = 0xFFFFFF
    graph_colour: Color = 0xFFFFFF
    graph_interval: datetime.timedelta = datetime.timedelta(days=1)


class StatusHistory(BaseModel):
    status_history_id: int
    created_at: datetime.datetime
    status_id: int
    online: bool

    max_players: int
    num_players: int
    down: bool

    players: list[StatusHistoryPlayer]


class StatusHistoryPlayer(BaseModel):
    status_history_player_id: int
    status_history_id: int
    name: str


class StatusQuery(BaseModel):
    status_query_id: int
    status_id: int
    host: Host
    game_port: int = Field(ge=0, lt=65536)
    query_port: int = Field(ge=0, lt=65536)
    type: StatusQueryType
    priority: int = Field(ge=0)

    enabled_at: datetime.datetime | None = Field(default=None)
    failed_at: datetime.datetime | None = Field(default=None)
    extra: str = ""


class StatusQueryType(StrEnum):
    ARMA_3 = "arma3"
    ARMA_REFORGER = "arma-reforger"
    MINECRAFT_BEDROCK = "minecraft-bedrock"
    MINECRAFT_JAVA = "minecraft-java"
    SOURCE = "source"
    PROJECT_ZOMBOID = "project-zomboid"

    @property
    def label(self) -> str:
        if self == StatusQueryType.ARMA_3:
            return "Arma 3"
        elif self == StatusQueryType.ARMA_REFORGER:
            return "Arma Reforger"
        elif self == StatusQueryType.MINECRAFT_BEDROCK:
            return "Minecraft (Bedrock Edition)"
        elif self == StatusQueryType.MINECRAFT_JAVA:
            return "Minecraft (Java Edition)"
        elif self == StatusQueryType.SOURCE:
            return "Valve Source Query (A2S)"
        elif self == StatusQueryType.PROJECT_ZOMBOID:
            return "Project Zomboid"
        else:
            assert_never(self)
