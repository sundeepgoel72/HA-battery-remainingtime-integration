"""Coordinator for Battery Remaining Time."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
from .events import BatteryEventState, detect_event_state
from .history import async_get_history_points
from .predictor import (
    BatteryInputs,
    BatteryPrediction,
    HistoryPoint,
    algorithm_spread,
    all_model_predictions,
    prediction_to_telemetry,
)
from .storage import BatteryStatsStore

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


def _latest_history_value(history: list[HistoryPoint], field: str) -> float | None:
    """Return the latest non-null value from recorder-derived history."""
    for point in reversed(history):
        value = getattr(point, field, None)
        if value is not None:
            return float(value)
    return None


class BatteryRemainingTimeCoordinator(DataUpdateCoordinator[BatteryPrediction]):
    """Coordinator that reads source entities and runs selected predictor."""

    config_entry: ConfigEntry
    event_state: BatteryEventState | None
    stats_store: BatteryStatsStore
    model_predictions: dict[str, BatteryPrediction]
    model_telemetry: dict[str, dict[str, float | str | None]]
    algorithm_spread: float | None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.config_entry = entry
        self._last_soc: float | None = None
        self._stats_loaded = False
        self.event_state = None
        self.model_predictions = {}
        self.model_telemetry = {}
        self.algorithm_spread = None
        self.stats_store = BatteryStatsStore(hass, entry.entry_id)
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
        if not self._stats_loaded:
            await self.stats_store.async_load()
            self._stats_loaded = True
            _LOGGER.info(
                "Loaded battery statistics: updates=%s anchors=%s",
                self.stats_store.stats.update_count,
                self.stats_store.stats.calibration_anchor_events,
            )

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

        # HA can call custom coordinators during startup before ESPHome/MQTT
        # source entities have restored their current states. Do not allow that
        # transient unavailability to seed SOC with a bogus 36-50% estimate.
        if voltage is None:
            voltage = _latest_history_value(history, "voltage")
            if voltage is not None:
                _LOGGER.info("Voltage sensor unavailable; using latest recorder voltage fallback=%s", voltage)
        if current is None:
            current = _latest_history_value(history, "current")
            if current is not None:
                _LOGGER.info("Current sensor unavailable; using latest recorder current fallback=%s", current)
        if charge_power is None:
            charge_power = _latest_history_value(history, "charge_power")
        if discharge_power is None:
            discharge_power = _latest_history_value(history, "discharge_power")
        if temperature is None:
            temperature = _latest_history_value(history, "temperature")

        no_live_or_history_voltage = voltage is None
        no_power_evidence = current is None and charge_power is None and discharge_power is None
        if no_live_or_history_voltage and no_power_evidence:
            _LOGGER.warning(
                "Skipping forecast update because source sensors are unavailable and recorder fallback is insufficient"
            )
            raise UpdateFailed("Battery source sensors unavailable; keeping previous forecast")

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
            model_accuracy=self.stats_store.stats.model_accuracy,
        )
        self.model_predictions = all_model_predictions(inputs)
        self.model_telemetry = {
            algorithm: prediction_to_telemetry(prediction)
            for algorithm, prediction in self.model_predictions.items()
        }
        self.algorithm_spread = algorithm_spread(self.model_predictions)
        result = self.model_predictions.get(selected_algorithm) or self.model_predictions[DEFAULT_ALGORITHM]

        _LOGGER.debug(
            "Model comparison: spread=%s outputs=%s accuracy=%s",
            self.algorithm_spread,
            {algorithm: telemetry.get("soc_percent") for algorithm, telemetry in self.model_telemetry.items()},
            self.stats_store.stats.model_accuracy,
        )

        self.event_state = detect_event_state(inputs, result)
        _LOGGER.debug(
            "Battery event state: state=%s evidence=%s anchor=%s",
            self.event_state.state,
            self.event_state.evidence,
            self.event_state.calibration_anchor,
        )
        if self.event_state.calibration_anchor:
            _LOGGER.info("Calibration evidence detected: state=%s evidence=%s", self.event_state.state, self.event_state.evidence)

        await self.stats_store.async_record_update(inputs, result, self.event_state, self.model_predictions)
        _LOGGER.debug(
            "Persistent stats updated: updates=%s anchors=%s model_accuracy=%s",
            self.stats_store.stats.update_count,
            self.stats_store.stats.calibration_anchor_events,
            self.stats_store.stats.model_accuracy,
        )

        if result.soc_percent is not None:
            self._last_soc = result.soc_percent
        else:
            _LOGGER.warning("Forecast returned no SOC estimate")

        if result.confidence == "low":
            _LOGGER.warning("Low confidence forecast: algorithm=%s reason=%s", result.algorithm, result.reason)
        else:
            _LOGGER.info(
                "Forecast updated: algorithm=%s soc=%s%% mode=%s tte=%sh ttf=%sh confidence=%s spread=%s",
                result.algorithm,
                result.soc_percent,
                result.mode,
                result.time_to_empty_h,
                result.time_to_full_h,
                result.confidence,
                self.algorithm_spread,
            )
        _LOGGER.debug("Forecast detail: net_power=%s reason=%s", result.net_power_w, result.reason)
        return result
