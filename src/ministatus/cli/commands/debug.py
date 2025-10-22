import sys

import click


@click.group(hidden=True)
def debug() -> None:
    """Internal debugging utilities."""


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
