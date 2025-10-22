import pkgutil


def list_extensions() -> list[str]:
    return [info.name for info in pkgutil.iter_modules(__path__, f"{__name__}.")]
