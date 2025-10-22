import importlib.resources
import logging
import re
import sys
from abc import ABC, abstractmethod
from typing import Iterable, NamedTuple, Self

from ministatus.db.connection import Connection, SQLiteConnection

log = logging.getLogger(__name__)


class Migration(NamedTuple):
    version: int
    sql: str


class Migrations(tuple[Migration, ...]):
    def after_version(self, version: int) -> Self:
        """Return a copy of self with only migrations after the given version."""
        return type(self)(m for m in self if m.version > version)

    def version_exists(self, version: int) -> bool:
        return any(m.version == version for m in self)

    @classmethod
    def from_iterable_unsorted(cls, it: Iterable[Migration]) -> Self:
        return cls(sorted(it, key=lambda m: m.version))


def read_migrations() -> Migrations:
    migrations: list[Migration] = [Migration(version=-1, sql="")]

    assert __package__ is not None
    path = importlib.resources.files(__package__).joinpath("migrations/")

    for file in path.iterdir():
        if not file.is_file():
            continue

        m = re.fullmatch(r"(\d+)-(.+)\.sql", file.name)
        if m is None:
            continue

        version = int(m[1])
        sql = file.read_text("utf-8")
        migrations.append(Migration(version=version, sql=sql))

    return Migrations.from_iterable_unsorted(migrations)


class Migrator(ABC):
    conn: Connection

    @abstractmethod
    async def get_version(self) -> int: ...

    @abstractmethod
    async def set_version(self, version: int, /) -> None: ...

    async def run_migrations(self, migrations: Migrations) -> None:
        version = await self.get_version()
        if version > 0 and not migrations.version_exists(version):
            sys.exit(f"Unrecognized database version: {version}")
            return

        for version, script in migrations.after_version(version):
            log.info(f"Migrating database to v{version}")
            await self.conn.executescript(script)

        await self.set_version(version)


class SQLiteMigrator(Migrator):
    def __init__(self, conn: SQLiteConnection) -> None:
        self.conn = conn

    async def get_version(self) -> int:
        return await self.conn.fetchval("PRAGMA user_version")

    async def set_version(self, version: int) -> None:
        await self.conn.fetchval(f"PRAGMA user_version = {version:d}")
