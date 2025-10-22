import asyncio
import functools
from typing import Any, Callable, Coroutine, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def mark_async():
    def deco(func: Callable[P, Coroutine[Any, Any, T]]):
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return asyncio.run(func(*args, **kwargs))

        return wrapper

    return deco
