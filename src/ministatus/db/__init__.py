from contextlib import asynccontextmanager
from typing import AsyncIterator

from ministatus.appdirs import DB_PATH

from .client import DatabaseClient as DatabaseClient
from .connection import (
    Connection as Connection,
    Record as Record,
    SQLiteConnection as SQLiteConnection,
)
from .migrations import (
    Migration as Migration,
    Migrations as Migrations,
    Migrator as Migrator,
    SQLiteMigrator as SQLiteMigrator,
    read_migrations as read_migrations,
)
from .secret import Secret as Secret


@asynccontextmanager
async def connect(*, transaction: bool = True) -> AsyncIterator[SQLiteConnection]:
    import asqlite

    database = str(DB_PATH)
    async with asqlite.connect(database) as conn:
        wrapped = SQLiteConnection(conn)
        if transaction:
            async with wrapped.transaction():
                yield wrapped
        else:
            yield wrapped


@asynccontextmanager
async def connect_client(*, transaction: bool = True) -> AsyncIterator[DatabaseClient]:
    async with connect(transaction=transaction) as conn:
        yield DatabaseClient(conn)


async def run_migrations() -> None:
    migrations = read_migrations()
    async with connect() as conn:
        migrator = SQLiteMigrator(conn)
        await migrator.run_migrations(migrations)
