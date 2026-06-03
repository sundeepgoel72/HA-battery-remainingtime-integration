"""Runtime configuration helpers for Battery Remaining Time."""

from __future__ import annotations

from typing import Any

def runtime_config(entry: Any) -> dict[str, Any]:
    """Return config entry data with options taking precedence."""
    return {**entry.data, **entry.options}
