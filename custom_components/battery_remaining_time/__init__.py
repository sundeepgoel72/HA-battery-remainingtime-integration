"""Battery Remaining Time integration."""

from __future__ import annotations

from typing import Any

from .const import DOMAIN, PLATFORMS
from .coordinator import BatteryRemainingTimeCoordinator


async def _async_update_listener(hass: Any, entry: Any) -> None:
    """Reload entry when options or config data change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up Battery Remaining Time from a config entry."""
    coordinator = BatteryRemainingTimeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
