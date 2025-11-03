from __future__ import annotations

import logging
import textwrap
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Iterable,
    Iterator,
    Literal,
    Protocol,
    Self,
    Sequence,
    TypeVar,
    assert_never,
)

if TYPE_CHECKING:
    import sqlite3

    import asqlite

T = TypeVar("T")
TransactionMode = bool | Literal["read", "write"]

LOG_QUERIES = False
log = logging.getLogger(__name__)


class Record(Protocol):
    def keys(self) -> Iterable[str]: ...
    def __getitem__(self, index: int | str, /) -> Any: ...
    def __iter__(self) -> Iterator[Any]: ...
    def __contains__(self, x: object, /) -> bool: ...
    def __len__(self) -> int: ...


class Connection(Protocol):
    async def execute(self, query: str, /, *args: object) -> Any: ...
    async def executemany(
        self,
        query: str,
        args: Iterable[Iterable[object]],
        /,
    ) -> Any: ...
    async def executescript(self, query: str, /) -> Any: ...
    async def fetch(self, query: str, /, *args: object) -> Sequence[Record]: ...
    async def fetchrow(self, query: str, /, *args: object) -> Record | None: ...
    async def fetchval(self, query: str, /, *args: object) -> Any: ...
    def transaction(
        self,
        mode: TransactionMode,
        /,
    ) -> AbstractAsyncContextManager[Self]: ...


class SQLiteConnection(Connection):
    def __init__(self, conn: asqlite.Connection) -> None:
        self.conn = conn

    async def execute(self, query: str, /, *args: object) -> None:
        if LOG_QUERIES:
            log.debug("SQL execute: %s", query)

        async with self.conn.execute(query, *args):
            return

    async def executemany(
        self,
        query: str,
        args: Iterable[Iterable[object]],
        /,
    ) -> None:
        if LOG_QUERIES:
            log.debug("SQL executemany: %s", query)

        async with self.conn.executemany(query, args):
            return

    async def executescript(self, query: str) -> None:
        if LOG_QUERIES:
            log.debug("SQL executescript: %s", textwrap.shorten(query, 200))

        async with self.conn.executescript(query):
            return

    async def fetch(self, query: str, /, *args: object) -> Sequence[sqlite3.Row]:
        if LOG_QUERIES:
            log.debug("SQL fetch: %s", query)

        return await self.conn.fetchall(query, *args)

    async def fetchrow(self, query: str, /, *args: object) -> sqlite3.Row | None:
        if LOG_QUERIES:
            log.debug("SQL fetchrow: %s", query)

        return await self.conn.fetchone(query, *args)

    async def fetchval(self, query: str, /, *args: object) -> Any:
        if LOG_QUERIES:
            log.debug("SQL fetchval: %s", query)

        row = await self.conn.fetchone(query, *args)
        if row is not None:
            return row[0]

    @asynccontextmanager
    async def transaction(
        self,
        mode: TransactionMode,
    ) -> AsyncIterator[Self]:
        if mode is False:
            yield self
        elif mode in (True, "read"):
            async with self.conn.transaction():
                yield self
        elif mode == "write":
            await self.conn.execute("BEGIN IMMEDIATE TRANSACTION")
            try:
                yield self
            except BaseException:
                await self.conn.rollback()
                raise
            else:
                await self.conn.commit()

        else:
            assert_never(mode)
