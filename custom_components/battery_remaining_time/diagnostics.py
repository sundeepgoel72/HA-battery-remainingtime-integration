"""Diagnostics support for Battery Remaining Time."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BATTERY_BRAND_MODEL,
    CONF_CHARGE_POWER_SENSOR,
    CONF_CURRENT_SENSOR,
    CONF_DISCHARGE_POWER_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_VOLTAGE_SENSOR,
    DOMAIN,
)
from .predictor import prediction_to_telemetry
from .runtime import runtime_config

TO_REDACT = {
    CONF_NAME,
    CONF_VOLTAGE_SENSOR,
    CONF_CURRENT_SENSOR,
    CONF_CHARGE_POWER_SENSOR,
    CONF_DISCHARGE_POWER_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_BATTERY_BRAND_MODEL,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, object]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    stats = coordinator.stats_store.stats
    profile = coordinator.stats_store.optimized_profile(stats.configured_capacity_ah or 0.0)
    event_state = coordinator.event_state

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
            "runtime_config": async_redact_data(dict(runtime_config(entry)), TO_REDACT),
        },
        "prediction": prediction_to_telemetry(coordinator.data) if coordinator.data is not None else None,
        "event_state": {
            "state": event_state.state,
            "evidence": list(event_state.evidence),
            "calibration_anchor": event_state.calibration_anchor,
        }
        if event_state is not None
        else None,
        "algorithm_spread": coordinator.algorithm_spread,
        "model_telemetry": coordinator.model_telemetry,
        "model_weighting": coordinator.model_weighting,
        "ensemble_weights": coordinator.ensemble_weights,
        "profile_optimization": profile,
        "stats": stats.as_dict(),
    }
