from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable

from ministatus import state
from ministatus.appdirs import DB_PATH

from . import converters as converters
from .client import DatabaseClient as DatabaseClient
from .connection import (
    Connection as Connection,
    Record as Record,
    SQLiteConnection as SQLiteConnection,
)
from .errors import (
    DatabaseEncryptedError as DatabaseEncryptedError,
    EncryptionUnsupportedError as EncryptionUnsupportedError,
)
from .migrations import (
    Migration as Migration,
    Migrations as Migrations,
    Migrator as Migrator,
    SQLiteMigrator as SQLiteMigrator,
    read_migrations as read_migrations,
)
from .models import (
    DiscordChannel as DiscordChannel,
    DiscordGuild as DiscordGuild,
    DiscordMember as DiscordMember,
    DiscordMessage as DiscordMessage,
    Status as Status,
    StatusAlert as StatusAlert,
    StatusDisplay as StatusDisplay,
    StatusQuery as StatusQuery,
    StatusQueryType as StatusQueryType,
    DiscordUser as DiscordUser,
)
from .secret import Secret as Secret
from .status import (
    fetch_statuses as fetch_statuses,
    fetch_status_alerts as fetch_status_alerts,
    fetch_status_displays as fetch_status_displays,
    fetch_status_queries as fetch_status_queries,
)

if TYPE_CHECKING:
    import asqlite

log = logging.getLogger(__name__)


@asynccontextmanager
async def connect(*, transaction: bool = True) -> AsyncIterator[SQLiteConnection]:
    database = str(DB_PATH)
    async with _connect(database, preinit=maybe_encrypt) as conn:
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


# Derived from asqlite.connect(), v2.0.0
def _connect(
    database: str,
    *,
    preinit: Callable[[sqlite3.Connection], Any],
    timeout: float | None = None,
    **kwargs: Any,
) -> asqlite._ContextManagerMixin[sqlite3.Connection, asqlite.Connection]:
    import asyncio
    import sqlite3
    from unittest.mock import patch

    import asqlite

    loop = asyncio.get_event_loop()
    queue = asqlite._Worker(loop=loop)
    queue.start()
    _real_connect = sqlite3.connect

    def factory(con: sqlite3.Connection) -> asqlite.Connection:
        return asqlite.Connection(con, queue)

    def patched_connect(*args, **kwargs) -> sqlite3.Connection:
        conn = _real_connect(*args, **kwargs)
        preinit(conn)
        return conn

    def new_connect(db: str, **kwargs: Any) -> sqlite3.Connection:
        with patch("sqlite3.connect", patched_connect):
            conn = asqlite._connect_pragmas(db, **kwargs)
        return conn

    return asqlite._ContextManagerMixin(
        queue,
        factory,
        new_connect,
        database,
        timeout=timeout,
        **kwargs,
    )


def maybe_encrypt(conn: sqlite3.Connection) -> None:
    if state.DB_PASSWORD is not None:
        encrypt(conn, state.DB_PASSWORD)


def encrypt(
    conn: sqlite3.Connection,
    password: Secret[str],
    *,
    rekey: bool = False,
) -> None:
    # Key formats:
    # https://www.zetetic.net/sqlcipher/sqlcipher-api/#PRAGMA_key
    # https://utelle.github.io/SQLite3MultipleCiphers/docs/configuration/config_sql_pragmas/#pragma-key--hexkey
    key = password.get_secret_value()
    key = key.replace("'", "''")
    pragma = "rekey" if rekey else "key"

    try:
        if rekey:
            conn.execute("PRAGMA journal_mode = delete")

        c = conn.execute(f"PRAGMA {pragma} = '{key}'")

        if not rekey:
            conn.execute("SELECT * FROM sqlite_schema")  # Test decryption
    except sqlite3.DatabaseError as e:
        if e.sqlite_errorcode == 26:  # SQLITE_NOTADB
            raise DatabaseEncryptedError() from None
        raise

    ret = c.fetchone()
    c.close()
    if ret is None:
        raise EncryptionUnsupportedError()  # Expected 'ok' to be returned
