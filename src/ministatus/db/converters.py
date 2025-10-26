# https://docs.python.org/3/library/sqlite3.html#adapter-and-converter-recipes
import datetime
import sqlite3


def adapt_date_iso(val: datetime.date) -> str:
    """Adapt datetime.date to ISO 8601 date."""
    return val.isoformat()


def adapt_datetime_iso(val: datetime.datetime) -> str:
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    val = val.astimezone(datetime.timezone.utc)
    return val.replace(tzinfo=None).isoformat()


def adapt_datetime_epoch(val: datetime.datetime) -> int:
    """Adapt datetime.datetime to Unix timestamp."""
    return max(int(val.timestamp()), 0)


# Can't set multiple adapters for one type, so just use timestamp for datetimes
sqlite3.register_adapter(datetime.date, adapt_date_iso)
# sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)
sqlite3.register_adapter(datetime.datetime, adapt_datetime_epoch)


def convert_date(val: bytes) -> datetime.date:
    """Convert ISO 8601 date to datetime.date object."""
    return datetime.date.fromisoformat(val.decode())


def convert_datetime(val: bytes) -> datetime.datetime:
    """Convert ISO 8601 datetime to datetime.datetime object."""
    dt = datetime.datetime.fromisoformat(val.decode())
    if dt.tzinfo:
        return dt.astimezone(datetime.timezone.utc)
    return dt.replace(tzinfo=datetime.timezone.utc)


def convert_timestamp(val: bytes) -> datetime.datetime:
    """Convert Unix epoch timestamp to datetime.datetime object."""
    ts = int(val)
    dt = datetime.datetime.fromtimestamp(ts)

    if ts < 86400:
        # The unix epoch probably got inserted into the database somehow...
        # Calling .astimezone() on this can cause an OSError for systems
        # with negative timezones, so we're just going to force the UTC
        # timezone on it. This changes the actual time being represented!
        return dt.replace(tzinfo=datetime.timezone.utc)

    return dt.astimezone(datetime.timezone.utc)


sqlite3.register_converter("date", convert_date)
sqlite3.register_converter("datetime", convert_datetime)
sqlite3.register_converter("timestamp", convert_timestamp)
