"""Coordinator for Battery Remaining Time."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
import logging

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ALGORITHM,
    CONF_BATTERY_CAPACITY_AH,
    CONF_CHARGE_POWER_SENSOR,
    CONF_CURRENT_SENSOR,
    CONF_DEPLETION_VOLTAGE,
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
    lower_confidence,
    rebuild_prediction_with_soc,
    confidence_from_spread,
    ensemble_model_weighting_strategy,
    ensemble_model_weights,
    prediction_to_telemetry,
)
from .runtime import runtime_config
from .storage import BatteryStatsStore

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
ISSUE_SOURCE_UNAVAILABLE = "source_unavailable"


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
    ensemble_weights: dict[str, float]
    model_weighting: dict[str, float | int | str | bool]
    source_evidence_status: str
    calibration_allowed: bool

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.config_entry = entry
        self._last_soc: float | None = None
        self._stats_loaded = False
        self.event_state = None
        self.model_predictions = {}
        self.model_telemetry = {}
        self.algorithm_spread = None
        self.ensemble_weights = {}
        self.model_weighting = {}
        self.source_evidence_status = "unknown"
        self.calibration_allowed = False
        self.stats_store = BatteryStatsStore(hass, entry.entry_id)
        data = runtime_config(entry)
        self._last_history_fetch_timestamp: datetime | None = None
        interval = int(data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
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

        data: dict[str, Any] = runtime_config(self.config_entry)
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
        history = await async_get_history_points(self.hass, entity_map, history_window, self._last_history_fetch_timestamp)
        latest_history_timestamp = _latest_history_timestamp(history)
        if latest_history_timestamp is not None:
            self._last_history_fetch_timestamp = latest_history_timestamp
        if not history:
            _LOGGER.warning("No recorder history points found; using current battery states only")
        else:
            _LOGGER.debug("Recorder history points available: %s", len(history))

        live_voltage = _state_float(self.hass, data.get(CONF_VOLTAGE_SENSOR))
        live_current = _state_float(self.hass, data.get(CONF_CURRENT_SENSOR))
        live_charge_power = _state_float(self.hass, data.get(CONF_CHARGE_POWER_SENSOR))
        live_discharge_power = _state_float(self.hass, data.get(CONF_DISCHARGE_POWER_SENSOR))
        live_temperature = _state_float(self.hass, data.get(CONF_TEMPERATURE_SENSOR))
        voltage = live_voltage
        current = live_current
        charge_power = live_charge_power
        discharge_power = live_discharge_power
        temperature = live_temperature

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

        used_recorder_fallback = any(
            (
                live_voltage is None and voltage is not None,
                live_current is None and current is not None,
                live_charge_power is None and charge_power is not None,
                live_discharge_power is None and discharge_power is not None,
                live_temperature is None and temperature is not None,
            )
        )
        self.source_evidence_status = (
            "live"
            if live_voltage is not None and (live_current is not None or live_charge_power is not None or live_discharge_power is not None)
            else "recorder_fallback"
            if used_recorder_fallback
            else "insufficient"
        )

        no_live_or_history_voltage = voltage is None
        no_power_evidence = current is None and charge_power is None and discharge_power is None
        if no_live_or_history_voltage and no_power_evidence:
            _LOGGER.warning(
                "Skipping forecast update because source sensors are unavailable and recorder fallback is insufficient"
            )
            self._create_source_issue()
            raise UpdateFailed("Battery source sensors unavailable; keeping previous forecast")

        if voltage is None:
            _LOGGER.warning("Voltage sensor is missing or unavailable; SOC estimate may be degraded")
        if current is None and charge_power is None and discharge_power is None:
            _LOGGER.warning("No current or power sensors available; runtime prediction may be unavailable")
        self._delete_source_issue()

        _LOGGER.debug(
            "Input snapshot: voltage=%s current=%s charge_power=%s discharge_power=%s temperature=%s previous_soc=%s",
            voltage,
            current,
            charge_power,
            discharge_power,
            temperature,
            self._last_soc,
        )
        configured_capacity_ah = float(data[CONF_BATTERY_CAPACITY_AH])
        configured_depletion_voltage = float(data[CONF_DEPLETION_VOLTAGE]) if data.get(CONF_DEPLETION_VOLTAGE) not in (None, "") else None
        optimized_profile = self.stats_store.optimized_profile(configured_capacity_ah, configured_depletion_voltage)

        inputs = BatteryInputs(
            algorithm=selected_algorithm,
            capacity_ah=float(optimized_profile["effective_capacity_ah"]),
            nominal_voltage=float(data[CONF_NOMINAL_VOLTAGE]),
            depletion_voltage=optimized_profile["effective_depletion_voltage"],
            voltage=voltage,
            current=current,
            charge_power=charge_power,
            discharge_power=discharge_power,
            temperature=temperature,
            history_window_minutes=history_window,
            peukert_exponent=self.stats_store.effective_peukert_exponent(),
            charge_efficiency=float(optimized_profile["effective_charge_efficiency"]),
            previous_soc_percent=self._last_soc,
            history=history,
            model_accuracy=self.stats_store.stats.model_accuracy,
        )
        self.model_predictions = all_model_predictions(inputs)
        self.ensemble_weights = ensemble_model_weights(inputs, self.model_predictions)
        self.model_weighting = ensemble_model_weighting_strategy(inputs, self.model_predictions)
        self.model_telemetry = {
            algorithm: prediction_to_telemetry(prediction)
            for algorithm, prediction in self.model_predictions.items()
        }
        self.algorithm_spread = algorithm_spread(self.model_predictions)
        result = self.model_predictions.get(selected_algorithm) or self.model_predictions[DEFAULT_ALGORITHM]
        spread_confidence = confidence_from_spread(
            self.algorithm_spread,
            sum(1 for prediction in self.model_predictions.values() if prediction.soc_percent is not None),
        )
        result = replace(result, confidence=lower_confidence(result.confidence, spread_confidence))
        result = _rate_limit_prediction(inputs, result, self._last_soc, self.algorithm_spread, self.source_evidence_status)
        if result.soc_percent is None and self.data is not None and self.data.soc_percent is not None:
            result = replace(
                self.data,
                confidence="very_low",
                reason=f"preserved last valid SOC; {result.reason}",
            )

        _LOGGER.debug(
            "Model comparison: spread=%s outputs=%s accuracy=%s weights=%s optimized_profile=%s",
            self.algorithm_spread,
            {algorithm: telemetry.get("soc_percent") for algorithm, telemetry in self.model_telemetry.items()},
            self.stats_store.stats.model_accuracy,
            self.ensemble_weights,
            optimized_profile,
        )
        _log_model_outputs(self.model_predictions, selected_algorithm, self.algorithm_spread, result.confidence)

        self.event_state = detect_event_state(inputs, result)
        self.calibration_allowed = _calibration_allowed(
            confidence=result.confidence,
            spread=self.algorithm_spread,
            source_evidence_status=self.source_evidence_status,
        )
        if self.event_state.calibration_anchor and not self.calibration_allowed:
            self.event_state = BatteryEventState(
                state=self.event_state.state,
                evidence=[*self.event_state.evidence, "calibration_blocked_untrusted_prediction"],
                calibration_anchor=False,
            )
        _LOGGER.debug(
            "Battery event state: state=%s evidence=%s anchor=%s calibration_allowed=%s source_evidence=%s",
            self.event_state.state,
            self.event_state.evidence,
            self.event_state.calibration_anchor,
            self.calibration_allowed,
            self.source_evidence_status,
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

    def _create_source_issue(self) -> None:
        """Create a user-facing repair issue for missing source evidence."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"{self.config_entry.entry_id}_{ISSUE_SOURCE_UNAVAILABLE}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_SOURCE_UNAVAILABLE,
        )

    def _delete_source_issue(self) -> None:
        """Clear source evidence repair issue once readings are usable."""
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{self.config_entry.entry_id}_{ISSUE_SOURCE_UNAVAILABLE}",
        )


def _latest_history_timestamp(history: list[HistoryPoint]) -> datetime | None:
    timestamps = [point.timestamp for point in history if point.timestamp is not None]
    if not timestamps:
        return None
    return max(timestamps)


def _calibration_allowed(*, confidence: str, spread: float | None, source_evidence_status: str) -> bool:
    """Return true when calibration anchors are safe to trust."""
    if confidence in {"low", "very_low"}:
        return False
    if spread is not None and spread > 15.0:
        return False
    return source_evidence_status == "live"


def _log_model_outputs(
    predictions: dict[str, BatteryPrediction],
    selected_algorithm: str,
    spread: float | None,
    confidence: str,
) -> None:
    """Log per-algorithm forecast outputs for field debugging."""
    aliases = {
        "voltage_only": "ocv",
        "current_flow": "coulomb",
        "peukert": "peukert",
        "hybrid_lead_acid": "hybrid",
        "ensemble": "ensemble",
    }
    payload: list[str] = []
    for algorithm, alias in aliases.items():
        prediction = predictions.get(algorithm)
        if prediction is None:
            continue
        payload.append(
            f"soc_{alias}={prediction.soc_percent} tte_{alias}={prediction.time_to_empty_h} ttf_{alias}={prediction.time_to_full_h}"
        )
    message = (
        f"Per-algorithm forecast: {'; '.join(payload)}; "
        f"active_algorithm={selected_algorithm} spread={spread} confidence={confidence}"
    )
    if spread is not None and spread > 30.0:
        _LOGGER.warning(message)
    else:
        _LOGGER.debug(message)


def _rate_limit_prediction(
    inputs: BatteryInputs,
    prediction: BatteryPrediction,
    previous_soc: float | None,
    spread: float | None,
    source_evidence_status: str,
) -> BatteryPrediction:
    """Clamp impossible one-step SOC moves on the selected output."""
    if previous_soc is None or prediction.soc_percent is None:
        return prediction
    max_step = 8.0 if prediction.mode in {"charging", "discharging"} else 2.0
    if spread is not None and spread > 30.0:
        max_step = min(max_step, 1.0)
    elif spread is not None and spread > 15.0:
        max_step = min(max_step, 2.0)
    if source_evidence_status != "live":
        max_step = min(max_step, 2.0)
    delta = prediction.soc_percent - previous_soc
    if abs(delta) <= max_step:
        return prediction
    limited_soc = round(previous_soc + (max_step if delta > 0 else -max_step), 1)
    return rebuild_prediction_with_soc(
        inputs,
        replace(prediction, confidence=lower_confidence(prediction.confidence, "low")),
        limited_soc,
        "; SOC rate-limited",
    )
