from __future__ import annotations

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Iterator,
    Protocol,
    Self,
    Sequence,
    TypeVar,
)

if TYPE_CHECKING:
    import sqlite3

    import asqlite

T = TypeVar("T")


class Record(Protocol):
    def __getitem__(self, index: int | str, /) -> Any: ...
    def __iter__(self) -> Iterator[Any]: ...
    def __contains__(self, x: object, /) -> bool: ...
    def __len__(self) -> int: ...


class Connection(Protocol):
    async def execute(self, query: str, /, *args: object) -> Any: ...
    async def executescript(self, query: str, /) -> Any: ...
    async def fetch(self, query: str, /, *args: object) -> Sequence[Record]: ...
    async def fetchrow(self, query: str, /, *args: object) -> Record | None: ...
    async def fetchval(self, query: str, /, *args: object) -> Any: ...
    def transaction(self) -> AbstractAsyncContextManager[Any]: ...


class SQLiteConnection(Connection):
    def __init__(self, conn: asqlite.Connection) -> None:
        self.conn = conn

    async def execute(self, query: str, /, *args: object) -> None:
        async with self.conn.execute(query, args):
            return

    async def executescript(self, query: str) -> None:
        async with self.conn.executescript(query):
            return

    async def fetch(self, query: str, /, *args: object) -> Sequence[sqlite3.Row]:
        return await self.conn.fetchall(query, args)

    async def fetchrow(self, query: str, /, *args: object) -> sqlite3.Row | None:
        return await self.conn.fetchone(query, args)

    async def fetchval(self, query: str, /, *args: object) -> Any:
        row = await self.fetchrow(query, *args)
        if row is not None:
            return row[0]

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asqlite.Transaction]:
        async with self.conn.transaction() as transaction:
            yield transaction

    @classmethod
    @asynccontextmanager
    async def connect(cls, database: str) -> AsyncIterator[Self]:
        async with asqlite.connect(database) as conn:
            yield cls(conn)
