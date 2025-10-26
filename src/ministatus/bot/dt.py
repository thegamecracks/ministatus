import datetime


def past(
    delta: datetime.timedelta | None = None,
    *,
    days: int = 0,
    seconds: int = 0,
    microseconds: int = 0,
    milliseconds: int = 0,
    minutes: int = 0,
    hours: int = 0,
    weeks: int = 0,
) -> datetime.datetime:
    kwargs_delta = datetime.timedelta(
        days=days,
        seconds=seconds,
        microseconds=microseconds,
        milliseconds=milliseconds,
        minutes=minutes,
        hours=hours,
        weeks=weeks,
    )
    if delta is None:
        return utcnow() - kwargs_delta
    return utcnow() - delta - kwargs_delta


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
