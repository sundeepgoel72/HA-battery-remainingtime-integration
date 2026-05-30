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
from .history import async_get_history_points
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
        _LOGGER.info("Battery Remaining Time initialized for '%s' with interval=%ss", entry.title, interval)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> BatteryPrediction:
        """Fetch source states, recorder history, and compute forecast."""
        data: dict[str, Any] = self.config_entry.data
        selected_algorithm = str(data.get(CONF_ALGORITHM, DEFAULT_ALGORITHM))
        history_window = int(data.get(CONF_HISTORY_WINDOW_MINUTES, DEFAULT_HISTORY_WINDOW_MINUTES))
        entity_map = {
            "voltage": data.get(CONF_VOLTAGE_SENSOR),
            "current": data.get(CONF_CURRENT_SENSOR),
            "charge_power": data.get(CONF_CHARGE_POWER_SENSOR),
            "discharge_power": data.get(CONF_DISCHARGE_POWER_SENSOR),
            "temperature": data.get(CONF_TEMPERATURE_SENSOR),
        }
        _LOGGER.debug("Forecast update started: algorithm=%s history_window=%s", selected_algorithm, history_window)
        history = await async_get_history_points(self.hass, entity_map, history_window)
        if not history:
            _LOGGER.warning("No recorder history points found; using current battery states only")
        else:
            _LOGGER.debug("Recorder history points available: %s", len(history))

        voltage = _state_float(self.hass, data.get(CONF_VOLTAGE_SENSOR))
        current = _state_float(self.hass, data.get(CONF_CURRENT_SENSOR))
        charge_power = _state_float(self.hass, data.get(CONF_CHARGE_POWER_SENSOR))
        discharge_power = _state_float(self.hass, data.get(CONF_DISCHARGE_POWER_SENSOR))
        temperature = _state_float(self.hass, data.get(CONF_TEMPERATURE_SENSOR))

        if voltage is None:
            _LOGGER.warning("Voltage sensor is missing or unavailable; SOC estimate may be degraded")
        if current is None and charge_power is None and discharge_power is None:
            _LOGGER.warning("No current or power sensors available; runtime prediction may be unavailable")

        _LOGGER.debug(
            "Input snapshot: voltage=%s current=%s charge_power=%s discharge_power=%s temperature=%s previous_soc=%s",
            voltage,
            current,
            charge_power,
            discharge_power,
            temperature,
            self._last_soc,
        )

        inputs = BatteryInputs(
            algorithm=selected_algorithm,
            capacity_ah=float(data[CONF_BATTERY_CAPACITY_AH]),
            nominal_voltage=float(data[CONF_NOMINAL_VOLTAGE]),
            voltage=voltage,
            current=current,
            charge_power=charge_power,
            discharge_power=discharge_power,
            temperature=temperature,
            history_window_minutes=history_window,
            previous_soc_percent=self._last_soc,
            history=history,
        )
        result = predict(inputs)
        if result.soc_percent is not None:
            self._last_soc = result.soc_percent
        else:
            _LOGGER.warning("Forecast returned no SOC estimate")

        if result.confidence == "low":
            _LOGGER.warning("Low confidence forecast: algorithm=%s reason=%s", result.algorithm, result.reason)
        else:
            _LOGGER.info(
                "Forecast updated: algorithm=%s soc=%s%% mode=%s tte=%sh ttf=%sh confidence=%s",
                result.algorithm,
                result.soc_percent,
                result.mode,
                result.time_to_empty_h,
                result.time_to_full_h,
                result.confidence,
            )
        _LOGGER.debug("Forecast detail: net_power=%s reason=%s", result.net_power_w, result.reason)
        return result
