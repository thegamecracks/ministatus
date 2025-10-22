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
    Migration,
    Migrations,
    Migrator,
    SQLiteMigrator,
    read_migrations,
)


@asynccontextmanager
async def connect() -> AsyncIterator[SQLiteConnection]:
    import asqlite

    database = str(DB_PATH)
    async with asqlite.connect(database) as conn:
        yield SQLiteConnection(conn)


async def run_migrations() -> None:
    migrations = read_migrations()
    async with connect() as conn:
        migrator = SQLiteMigrator(conn)
        await migrator.run_migrations(migrations)
