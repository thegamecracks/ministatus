class DatabaseEncryptedError(RuntimeError):
    """The database password is incorrect or may be corrupted."""

    def __init__(self) -> None:
        assert self.__doc__ is not None
        super().__init__(self.__doc__.partition("\n")[0])


class EncryptionUnsupportedError(RuntimeError):
    """The underlying sqlite3 library does not suport encryption."""

    def __init__(self) -> None:
        assert self.__doc__ is not None
        super().__init__(self.__doc__.partition("\n")[0])
