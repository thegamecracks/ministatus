# Global state smells...
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ministatus.db import Secret

DB_PASSWORD: Secret[str] | None = None
