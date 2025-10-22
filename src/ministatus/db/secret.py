from typing import Generic, TypeVar

T = TypeVar("T")


class Secret(Generic[T]):
    """A value wrapper over a secret to prevent accidentally printing it."""

    def __init__(self, value: T) -> None:
        self._value = value

    def __repr__(self) -> str:
        return f"{type(self).__name__}(value='****')"

    def __str__(self) -> str:
        return "****"

    def get_secret_value(self) -> T:
        return self._value
