"""Coordinator for Battery Remaining Time."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALGORITHM,
    CONF_BATTERY_CAPACITY_AH,
    CONF_CHARGE_POWER_SENSOR,
    CONF_CURRENT_SENSOR,
    CONF_DISCHARGE_POWER_SENSOR,
    CONF_HISTORY_WINDOW_MINUTES,
    CONF_NOMINAL_VOLTAGE,
    CONF_TEMPERATURE_SENSOR,
    CONF_UPDATE_INTERVAL,
    CONF_VOLTAGE_SENSOR,
    DEFAULT_ALGORITHM,
    DEFAULT_HISTORY_WINDOW_MINUTES,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .predictor import BatteryInputs, BatteryPrediction, predict

_LOGGER = logging.getLogger(__name__)


def _state_float(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Return entity state as float when available."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in {"unknown", "unavailable"}:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


class BatteryRemainingTimeCoordinator(DataUpdateCoordinator[BatteryPrediction]):
    """Coordinator that reads source entities and runs selected predictor."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.config_entry = entry
        self._last_soc: float | None = None
        interval = int(entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> BatteryPrediction:
        """Fetch source states and compute forecast."""
        data: dict[str, Any] = self.config_entry.data
        inputs = BatteryInputs(
            algorithm=str(data.get(CONF_ALGORITHM, DEFAULT_ALGORITHM)),
            capacity_ah=float(data[CONF_BATTERY_CAPACITY_AH]),
            nominal_voltage=float(data[CONF_NOMINAL_VOLTAGE]),
            voltage=_state_float(self.hass, data.get(CONF_VOLTAGE_SENSOR)),
            current=_state_float(self.hass, data.get(CONF_CURRENT_SENSOR)),
            charge_power=_state_float(self.hass, data.get(CONF_CHARGE_POWER_SENSOR)),
            discharge_power=_state_float(self.hass, data.get(CONF_DISCHARGE_POWER_SENSOR)),
            temperature=_state_float(self.hass, data.get(CONF_TEMPERATURE_SENSOR)),
            history_window_minutes=int(data.get(CONF_HISTORY_WINDOW_MINUTES, DEFAULT_HISTORY_WINDOW_MINUTES)),
            previous_soc_percent=self._last_soc,
            history=[],
        )
        result = predict(inputs)
        if result.soc_percent is not None:
            self._last_soc = result.soc_percent
        return result
