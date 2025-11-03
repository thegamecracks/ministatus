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

        params = self._transform_args(query, args)
        async with self.conn.execute(query, params):
            return

    async def executemany(
        self,
        query: str,
        args: Iterable[Iterable[object]],
        /,
    ) -> None:
        if LOG_QUERIES:
            log.debug("SQL executemany: %s", query)

        params = [self._transform_args(query, sub) for sub in args]
        async with self.conn.executemany(query, params):
            return

    async def executescript(self, query: str) -> None:
        if LOG_QUERIES:
            log.debug("SQL executescript: %s", textwrap.shorten(query, 200))

        async with self.conn.executescript(query):
            return

    async def fetch(self, query: str, /, *args: object) -> Sequence[sqlite3.Row]:
        if LOG_QUERIES:
            log.debug("SQL fetch: %s", query)

        params = self._transform_args(query, args)
        return await self.conn.fetchall(query, params)

    async def fetchrow(self, query: str, /, *args: object) -> sqlite3.Row | None:
        if LOG_QUERIES:
            log.debug("SQL fetchrow: %s", query)

        params = self._transform_args(query, args)
        return await self.conn.fetchone(query, params)

    async def fetchval(self, query: str, /, *args: object) -> Any:
        if LOG_QUERIES:
            log.debug("SQL fetchval: %s", query)

        params = self._transform_args(query, args)
        row = await self.conn.fetchone(query, params)
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

    @staticmethod
    def _transform_args(
        query: str,
        args: Iterable[object],
    ) -> dict[str, object] | tuple[object, ...]:
        # Used for Python 3.14+ compatibility
        if "$1" in query:
            return {str(i): x for i, x in enumerate(args, 1)}
        return tuple(args)
