import sqlite3
import sys

import click

from ministatus import state
from ministatus.appdirs import DB_PATH
from ministatus.db import Secret, encrypt as db_encrypt
from ministatus.db.errors import DatabaseEncryptedError, EncryptionUnsupportedError


ALREADY_DECRYPTED = click.style(
    "Database is already decrypted 😴",
    fg="yellow",
)
ALREADY_ENCRYPTED = click.style(
    "Database is already encrypted 😴",
    fg="yellow",
)
ENCRYPTION_NOT_SUPPORTED = click.style(
    "The current sqlite3 library does not support encryption 🙁",
    fg="red",
)
SUCCESSFUL_DECRYPTION = click.style(
    "Successfully decrypted!",
    fg="green",
)
SUCCESSFUL_ENCRYPTION = click.style(
    "Successfully encrypted!",
    fg="green",
)
WRONG_PASSWORD = click.style(
    "Database could not be decrypted. Wrong password?",
    fg="red",
)


@click.group()
def db() -> None:
    """Manage the application database."""


@db.command()
@click.argument("password", default=None, type=Secret)
def encrypt(password: Secret[str] | None) -> None:
    """Encrypt the database with a new password."""
    if state.DB_PASSWORD is not None:
        password = state.DB_PASSWORD
    elif password is None:
        password = click.prompt("Database Password", hide_input=True, type=Secret)
        assert isinstance(password, Secret)

    conn = sqlite3.connect(DB_PATH)

    try:
        db_encrypt(conn, password, rekey=True)
    except DatabaseEncryptedError:
        try:
            db_encrypt(conn, password)
            sys.exit(ALREADY_ENCRYPTED)
        except DatabaseEncryptedError:
            sys.exit(WRONG_PASSWORD)
    except EncryptionUnsupportedError:
        sys.exit(ENCRYPTION_NOT_SUPPORTED)

    click.echo(SUCCESSFUL_ENCRYPTION)


@db.command()
@click.argument("old", default=None, type=Secret)
@click.argument("new", default=None, type=Secret)
def reencrypt(old: Secret[str] | None, new: Secret[str] | None) -> None:
    """Re-encrypt the database with a new password."""
    conn = sqlite3.connect(DB_PATH)

    try:
        db_encrypt(conn, Secret(""))
        click.echo(ALREADY_DECRYPTED)
    except DatabaseEncryptedError:
        _decrypt_old(conn, old)
    except EncryptionUnsupportedError:
        sys.exit(ENCRYPTION_NOT_SUPPORTED)

    if new is None or not new.get_secret_value():
        new = click.prompt("New Password", hide_input=True, type=Secret)
        assert isinstance(new, Secret)

    db_encrypt(conn, new, rekey=True)
    click.echo(SUCCESSFUL_ENCRYPTION)


def _decrypt_old(conn: sqlite3.Connection, old: Secret[str] | None):
    if state.DB_PASSWORD is not None:
        old = state.DB_PASSWORD
    elif old is None or not old.get_secret_value():
        old = click.prompt("Old Password", hide_input=True, type=Secret)
        assert isinstance(old, Secret)

    try:
        db_encrypt(conn, old)
    except DatabaseEncryptedError:
        sys.exit(WRONG_PASSWORD)


@db.command()
@click.argument("password", default=None, type=Secret)
def decrypt(password: Secret[str] | None) -> None:
    """Decrypt the database with an old password."""
    if state.DB_PASSWORD is not None:
        password = state.DB_PASSWORD
    elif password is None:
        password = click.prompt("Database Password", hide_input=True, type=Secret)
        assert isinstance(password, Secret)

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("SELECT * FROM sqlite_schema")
        sys.exit(ALREADY_DECRYPTED)
    except sqlite3.DatabaseError:
        pass

    try:
        db_encrypt(conn, password)
        db_encrypt(conn, Secret(""), rekey=True)
    except DatabaseEncryptedError:
        sys.exit(WRONG_PASSWORD)
    except EncryptionUnsupportedError:
        sys.exit(ENCRYPTION_NOT_SUPPORTED)

    click.echo(SUCCESSFUL_DECRYPTION)
