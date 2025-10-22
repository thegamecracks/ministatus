from __future__ import annotations

import argparse
import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass
from string import Template
from typing import TYPE_CHECKING, Self, TypeAlias, overload

if TYPE_CHECKING:
    from ministatus.cli.config import Config

assert __package__ is not None
PROG = __package__.partition(".")[0]

SubParser: TypeAlias = "argparse._SubParsersAction[argparse.ArgumentParser]"


@dataclass
class Command(ABC):
    config: Config

    @classmethod
    @abstractmethod
    def register(cls, subparsers: SubParser) -> None: ...

    @classmethod
    @abstractmethod
    def from_config(cls, config: Config, /) -> Self: ...

    @abstractmethod
    def invoke(self) -> None: ...


@overload
def clean_doc(doc: str) -> str: ...


@overload
def clean_doc(doc: None) -> None: ...


def clean_doc(doc: str | None) -> str | None:
    if doc is None:
        return None

    first, _, rest = doc.partition("\n")
    rest = textwrap.dedent(rest)
    doc = f"{first}\n{rest}".strip()
    return Template(doc).safe_substitute(
        prog=PROG,
    )
