"""Runtime configuration helpers for Battery Remaining Time."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry


def runtime_config(entry: ConfigEntry) -> dict[str, Any]:
    """Return config entry data with options taking precedence."""
    return {**entry.data, **entry.options}
