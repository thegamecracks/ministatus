def _get_version() -> str:
    from importlib.metadata import version

    return version(_dist_name)


def _get_user_agent() -> str:
    from importlib.metadata import metadata
    from typing import cast

    meta = metadata(_dist_name)
    name = meta["Name"]
    version = meta["Version"]

    urls = cast(list[str], meta.get_all("Project-URL"))
    homepage = next((url for url in urls if url.startswith("Homepage")), urls[0])
    _, _, homepage = homepage.rpartition(", ")

    return f"{name}/{version} ({homepage})"


_dist_name = "ministatus"
__version__ = _get_version()
_user_agent = _get_user_agent()
