import asyncio
import functools
import sqlite3
import sys
from contextlib import closing
from typing import Any, Callable, Coroutine, ParamSpec, TypeVar

import click

from ministatus import state
from ministatus.appdirs import DB_PATH
from ministatus.db import (
    DatabaseEncryptedError,
    EncryptionUnsupportedError,
    Secret,
    encrypt,
    run_migrations,
)

P = ParamSpec("P")
T = TypeVar("T")

_migrations_ran = False


def mark_async():
    def deco(func: Callable[P, Coroutine[Any, Any, T]]):
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return asyncio.run(func(*args, **kwargs))

        return wrapper

    return deco


def mark_db():
    def deco(func: Callable[P, T]):
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            _maybe_run_migrations()
            return func(*args, **kwargs)

        return wrapper

    return deco


def _maybe_run_migrations() -> None:
    global _migrations_ran

    if _migrations_ran:
        return
    elif state.DB_PASSWORD is None:
        _maybe_set_database_password()
    else:
        _check_database_password(state.DB_PASSWORD)

    asyncio.run(run_migrations())
    _migrations_ran = True


def _maybe_set_database_password() -> None:
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            encrypt(conn, Secret(""))
    except DatabaseEncryptedError:
        password = click.prompt("Database Password", hide_input=True, type=Secret)
        state.DB_PASSWORD = password
    except EncryptionUnsupportedError:
        pass


def _check_database_password(password: Secret[str]) -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        try:
            encrypt(conn, Secret(""))
        except DatabaseEncryptedError:
            pass
        except EncryptionUnsupportedError:
            from ministatus.cli.commands.db import ENCRYPTION_NOT_SUPPORTED

            sys.exit(ENCRYPTION_NOT_SUPPORTED)
        else:
            # Attempted to use password on a decrypted database
            not_encrypted = click.style(
                "Database is not encrypted yet! "
                "Use 'db encrypt' or unset your password.",
                fg="red",
            )
            sys.exit(not_encrypted)

        try:
            encrypt(conn, password)
        except DatabaseEncryptedError:
            from ministatus.cli.commands.db import WRONG_PASSWORD

            sys.exit(WRONG_PASSWORD)
