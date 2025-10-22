import logging
import sys

import click


@click.group(hidden=True)
def debug() -> None:
    """Internal debugging utilities."""


@debug.command()
def levels() -> None:
    """Trigger info and debug logs to test logging verbosity."""
    logging.getLogger(__name__).info("Test 1")
    logging.getLogger(__name__).debug("Test 2")
    logging.getLogger().info("Test 3")
    logging.getLogger().debug("Test 4")


@debug.command()
def imports() -> None:
    """Print all third-party modules imported at startup."""
    names = sorted(
        name
        for name in sys.modules
        if name.partition(".")[0] not in sys.stdlib_module_names
        and name not in ("__main__", "_virtualenv")
    )

    packages: dict[str, list[str]] = {}
    for name in names:
        package, _, submodule = name.partition(".")
        packages.setdefault(package, [])
        if submodule:
            packages[package].append(submodule)

    for package, submodules in packages.items():
        click.secho(package, fg="green")
        for mod in submodules:
            click.secho(f"  .{mod}", fg="yellow")
