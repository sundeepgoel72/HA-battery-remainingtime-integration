"""Persistent statistics storage for Battery Remaining Time."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .events import BatteryEventState
from .predictor import BatteryInputs, BatteryPrediction

STORAGE_KEY = "battery_remaining_time"
STORAGE_VERSION = 1
MAX_HEALTH_OBSERVATIONS = 200
MAX_CAPACITY_OBSERVATIONS = 100
MAX_MODEL_PERFORMANCE_OBSERVATIONS = 200
MAX_ANCHOR_OBSERVATIONS = 200


@dataclass(slots=True)
class BatteryStats:
    """Persistent battery statistics and calibration evidence."""

    first_seen: str | None = None
    last_seen: str | None = None
    update_count: int = 0
    rest_events: int = 0
    float_events: int = 0
    absorption_events: int = 0
    low_battery_events: int = 0
    heavy_discharge_events: int = 0
    calibration_anchor_events: int = 0
    lowest_soc_percent: float | None = None
    highest_soc_percent: float | None = None
    lowest_voltage: float | None = None
    highest_voltage: float | None = None
    highest_charge_power: float | None = None
    highest_discharge_power: float | None = None
    highest_charge_current: float | None = None
    highest_discharge_current: float | None = None
    event_counts: dict[str, int] = field(default_factory=dict)

    battery_health_percent: float | None = None
    useful_life_percent: float | None = None
    health_confidence: str = "low"
    health_observation_count: int = 0
    estimated_cycle_equivalents: float = 0.0
    cumulative_discharge_ah: float = 0.0
    cumulative_charge_ah: float = 0.0
    last_health_observation: dict[str, Any] = field(default_factory=dict)
    recent_health_observations: list[dict[str, Any]] = field(default_factory=list)

    configured_capacity_ah: float | None = None
    learned_capacity_ah: float | None = None
    capacity_retention_percent: float | None = None
    capacity_confidence: str = "low"
    capacity_observation_count: int = 0
    capacity_observations: list[dict[str, Any]] = field(default_factory=list)
    last_capacity_anchor: dict[str, Any] = field(default_factory=dict)

    learned_full_voltage: float | None = None
    learned_empty_voltage: float | None = None
    full_voltage_observation_count: int = 0
    empty_voltage_observation_count: int = 0
    learned_charge_efficiency: float | None = None
    charge_efficiency_confidence: str = "low"
    charge_efficiency_observation_count: int = 0
    anchor_observations: list[dict[str, Any]] = field(default_factory=list)

    model_error_stats: dict[str, dict[str, float | int]] = field(default_factory=dict)
    model_accuracy: dict[str, float] = field(default_factory=dict)
    model_performance_observations: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BatteryStats":
        """Create stats from stored data."""
        if not data:
            return cls()
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def as_dict(self) -> dict[str, Any]:
        """Return serializable stats."""
        return asdict(self)


class BatteryStatsStore:
    """Home Assistant storage wrapper for battery statistics."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
        self.stats = BatteryStats()

    async def async_load(self) -> None:
        """Load stored stats."""
        self.stats = BatteryStats.from_dict(await self._store.async_load())

    async def async_save(self) -> None:
        """Persist current stats."""
        await self._store.async_save(self.stats.as_dict())

    async def async_record_update(
        self,
        inputs: BatteryInputs,
        prediction: BatteryPrediction,
        event_state: BatteryEventState | None,
        model_predictions: dict[str, BatteryPrediction] | None = None,
    ) -> None:
        """Record one forecast cycle."""
        now = datetime.now(timezone.utc).isoformat()
        if self.stats.first_seen is None:
            self.stats.first_seen = now
        self.stats.last_seen = now
        self.stats.update_count += 1
        self.stats.configured_capacity_ah = round(inputs.capacity_ah, 3)

        if prediction.soc_percent is not None:
            self.stats.lowest_soc_percent = _min_optional(self.stats.lowest_soc_percent, prediction.soc_percent)
            self.stats.highest_soc_percent = _max_optional(self.stats.highest_soc_percent, prediction.soc_percent)

        if inputs.voltage is not None:
            self.stats.lowest_voltage = _min_optional(self.stats.lowest_voltage, inputs.voltage)
            self.stats.highest_voltage = _max_optional(self.stats.highest_voltage, inputs.voltage)
        if inputs.charge_power is not None:
            self.stats.highest_charge_power = _max_optional(self.stats.highest_charge_power, inputs.charge_power)
        if inputs.discharge_power is not None:
            self.stats.highest_discharge_power = _max_optional(self.stats.highest_discharge_power, inputs.discharge_power)
        if inputs.current is not None:
            if inputs.current > 0:
                self.stats.highest_charge_current = _max_optional(self.stats.highest_charge_current, inputs.current)
            if inputs.current < 0:
                self.stats.highest_discharge_current = _max_optional(self.stats.highest_discharge_current, abs(inputs.current))

        self._record_health_observation(now, inputs, prediction, event_state)
        self._record_anchor_observation(now, inputs, prediction, event_state)
        self._record_capacity_observation(now, inputs, prediction, event_state)
        self._record_model_performance(now, prediction, event_state, model_predictions)

        if event_state is not None:
            self.stats.event_counts[event_state.state] = self.stats.event_counts.get(event_state.state, 0) + 1
            if event_state.calibration_anchor:
                self.stats.calibration_anchor_events += 1
            if event_state.state == "resting":
                self.stats.rest_events += 1
            elif event_state.state == "float":
                self.stats.float_events += 1
            elif event_state.state == "absorption":
                self.stats.absorption_events += 1
            elif event_state.state == "low_battery":
                self.stats.low_battery_events += 1
            elif event_state.state == "heavy_discharge":
                self.stats.heavy_discharge_events += 1

        await self.async_save()

    def _record_health_observation(
        self,
        now: str,
        inputs: BatteryInputs,
        prediction: BatteryPrediction,
        event_state: BatteryEventState | None,
    ) -> None:
        """Update learned health indicators from observed operating shape."""
        discharge_ah = 0.0
        charge_ah = 0.0
        discharge_wh = 0.0
        charge_wh = 0.0
        current_samples = 0
        voltage_samples = 0
        low_voltage_samples = 0
        high_discharge_samples = 0

        for point in inputs.history:
            dt_hours = max(point.dt_hours, 0.0)
            if dt_hours <= 0:
                continue
            current = point.current
            if current is None and point.voltage:
                if point.charge_power is not None:
                    current = point.charge_power / point.voltage
                elif point.discharge_power is not None:
                    current = -point.discharge_power / point.voltage
            if current is not None:
                current_samples += 1
                if current < 0:
                    discharge_ah += abs(current) * dt_hours
                    if point.voltage is not None:
                        discharge_wh += abs(current) * point.voltage * dt_hours
                elif current > 0:
                    charge_ah += current * dt_hours
                    if point.voltage is not None:
                        charge_wh += current * point.voltage * dt_hours
                if abs(current) > max(inputs.capacity_ah / 10.0, 1.0):
                    high_discharge_samples += 1
            if point.voltage is not None:
                voltage_samples += 1
                low_voltage_threshold = inputs.nominal_voltage * 0.98
                if point.voltage < low_voltage_threshold:
                    low_voltage_samples += 1

        if discharge_ah > 0:
            self.stats.cumulative_discharge_ah += discharge_ah
        if charge_ah > 0:
            self.stats.cumulative_charge_ah += charge_ah

        cycle_fraction = discharge_ah / max(inputs.capacity_ah, 0.1)
        if cycle_fraction > 0:
            self.stats.estimated_cycle_equivalents += cycle_fraction

        low_voltage_ratio = low_voltage_samples / voltage_samples if voltage_samples else 0.0
        high_discharge_ratio = high_discharge_samples / current_samples if current_samples else 0.0
        spread = None
        if prediction.soc_percent is not None:
            spread = abs(prediction.soc_percent - (inputs.previous_soc_percent or prediction.soc_percent))

        stress_score = 0.0
        stress_score += min(low_voltage_ratio * 35.0, 35.0)
        stress_score += min(high_discharge_ratio * 20.0, 20.0)
        stress_score += min(self.stats.low_battery_events * 1.5, 20.0)
        stress_score += min(self.stats.heavy_discharge_events * 1.0, 15.0)
        stress_score += min(max(self.stats.estimated_cycle_equivalents - 50.0, 0.0) * 0.05, 10.0)

        health = 100.0 - stress_score
        if self.stats.capacity_retention_percent is not None:
            health = min(health, self.stats.capacity_retention_percent)
        if voltage_samples < 20 and current_samples < 5:
            health = min(health, 95.0)
        health = _clamp(health, 0.0, 100.0)

        confidence = "low"
        if self.stats.estimated_cycle_equivalents >= 5 and self.stats.calibration_anchor_events >= 20:
            confidence = "medium"
        if self.stats.estimated_cycle_equivalents >= 20 and self.stats.low_battery_events > 0 and self.stats.calibration_anchor_events >= 50:
            confidence = "high"
        if self.stats.capacity_confidence == "high":
            confidence = "high"
        elif self.stats.capacity_confidence == "medium" and confidence == "low":
            confidence = "medium"

        observation = {
            "timestamp": now,
            "event_state": event_state.state if event_state else None,
            "calibration_anchor": event_state.calibration_anchor if event_state else False,
            "soc_percent": prediction.soc_percent,
            "voltage": inputs.voltage,
            "current": inputs.current,
            "discharge_ah_window": round(discharge_ah, 3),
            "charge_ah_window": round(charge_ah, 3),
            "discharge_wh_window": round(discharge_wh, 2),
            "charge_wh_window": round(charge_wh, 2),
            "cycle_fraction_window": round(cycle_fraction, 5),
            "low_voltage_ratio": round(low_voltage_ratio, 3),
            "high_discharge_ratio": round(high_discharge_ratio, 3),
            "stress_score": round(stress_score, 1),
            "health_percent": round(health, 1),
            "health_confidence": confidence,
            "soc_step_change": round(spread, 2) if spread is not None else None,
        }

        self.stats.health_observation_count += 1
        self.stats.battery_health_percent = round(health, 1)
        self.stats.useful_life_percent = round(health, 1)
        self.stats.health_confidence = confidence
        self.stats.last_health_observation = observation
        self.stats.recent_health_observations.append(observation)
        self.stats.recent_health_observations = self.stats.recent_health_observations[-MAX_HEALTH_OBSERVATIONS:]

    def _record_anchor_observation(
        self,
        now: str,
        inputs: BatteryInputs,
        prediction: BatteryPrediction,
        event_state: BatteryEventState | None,
    ) -> None:
        """Learn full/empty voltage and charge efficiency from calibration anchors."""
        if event_state is None or not event_state.calibration_anchor or prediction.soc_percent is None or inputs.voltage is None:
            return

        anchor = {
            "timestamp": now,
            "event_state": event_state.state,
            "soc_percent": prediction.soc_percent,
            "voltage": round(inputs.voltage, 4),
            "current": inputs.current,
            "cumulative_discharge_ah": round(self.stats.cumulative_discharge_ah, 4),
            "cumulative_charge_ah": round(self.stats.cumulative_charge_ah, 4),
        }
        self.stats.anchor_observations.append(anchor)
        self.stats.anchor_observations = self.stats.anchor_observations[-MAX_ANCHOR_OBSERVATIONS:]

        if prediction.soc_percent >= 95.0 and event_state.state in {"resting", "float", "absorption"}:
            self.stats.learned_full_voltage = _running_average(
                self.stats.learned_full_voltage,
                inputs.voltage,
                self.stats.full_voltage_observation_count,
            )
            self.stats.full_voltage_observation_count += 1
        elif prediction.soc_percent <= 25.0 and event_state.state in {"low_battery", "resting"}:
            self.stats.learned_empty_voltage = _running_average(
                self.stats.learned_empty_voltage,
                inputs.voltage,
                self.stats.empty_voltage_observation_count,
            )
            self.stats.empty_voltage_observation_count += 1

        previous = self.stats.last_capacity_anchor
        if not previous:
            return
        try:
            previous_soc = float(previous.get("soc_percent"))
            previous_charge_ah = float(previous.get("cumulative_charge_ah", 0.0))
            previous_discharge_ah = float(previous.get("cumulative_discharge_ah", 0.0))
        except (TypeError, ValueError):
            return

        charged_ah = self.stats.cumulative_charge_ah - previous_charge_ah
        discharged_ah = self.stats.cumulative_discharge_ah - previous_discharge_ah
        soc_gain = prediction.soc_percent - previous_soc
        if soc_gain >= 10.0 and charged_ah > 0 and discharged_ah >= 0:
            retained_ah = max((soc_gain / 100.0) * inputs.capacity_ah + discharged_ah, 0.0)
            efficiency = _clamp(retained_ah / max(charged_ah, 0.1), 0.50, 1.05)
            self.stats.learned_charge_efficiency = round(
                _running_average(
                    self.stats.learned_charge_efficiency,
                    efficiency,
                    self.stats.charge_efficiency_observation_count,
                ),
                3,
            )
            self.stats.charge_efficiency_observation_count += 1
            if self.stats.charge_efficiency_observation_count >= 5:
                self.stats.charge_efficiency_confidence = "high"
            elif self.stats.charge_efficiency_observation_count >= 2:
                self.stats.charge_efficiency_confidence = "medium"

    def _record_capacity_observation(
        self,
        now: str,
        inputs: BatteryInputs,
        prediction: BatteryPrediction,
        event_state: BatteryEventState | None,
    ) -> None:
        """Learn usable capacity from meaningful anchor-to-anchor discharge evidence."""
        if event_state is None or not event_state.calibration_anchor or prediction.soc_percent is None:
            return

        anchor = {
            "timestamp": now,
            "soc_percent": prediction.soc_percent,
            "voltage": inputs.voltage,
            "current": inputs.current,
            "event_state": event_state.state,
            "cumulative_discharge_ah": self.stats.cumulative_discharge_ah,
            "cumulative_charge_ah": self.stats.cumulative_charge_ah,
        }

        previous = self.stats.last_capacity_anchor
        if not previous:
            self.stats.last_capacity_anchor = anchor
            return

        try:
            previous_soc = float(previous.get("soc_percent"))
            previous_discharge_ah = float(previous.get("cumulative_discharge_ah", 0.0))
            previous_charge_ah = float(previous.get("cumulative_charge_ah", 0.0))
        except (TypeError, ValueError):
            self.stats.last_capacity_anchor = anchor
            return

        soc_delta = previous_soc - prediction.soc_percent
        discharged_ah = self.stats.cumulative_discharge_ah - previous_discharge_ah
        charged_ah = self.stats.cumulative_charge_ah - previous_charge_ah

        throughput_since_anchor = discharged_ah + charged_ah
        if abs(soc_delta) < 3.0 and throughput_since_anchor < max(inputs.capacity_ah * 0.02, 1.0):
            return

        self.stats.last_capacity_anchor = anchor

        if soc_delta < 8.0 or discharged_ah <= 0:
            return
        if charged_ah > discharged_ah * 0.50:
            return

        estimated_capacity = discharged_ah / max(soc_delta / 100.0, 0.01)
        if estimated_capacity <= 0:
            return

        lower_bound = inputs.capacity_ah * 0.35
        upper_bound = inputs.capacity_ah * 1.20
        if not lower_bound <= estimated_capacity <= upper_bound:
            return

        confidence = "low"
        if soc_delta >= 12.0 and discharged_ah >= inputs.capacity_ah * 0.06:
            confidence = "medium"
        if soc_delta >= 25.0 and discharged_ah >= inputs.capacity_ah * 0.15:
            confidence = "high"

        observation = {
            "timestamp": now,
            "start_anchor": previous,
            "end_anchor": anchor,
            "soc_delta_percent": round(soc_delta, 2),
            "discharged_ah": round(discharged_ah, 3),
            "charged_ah": round(charged_ah, 3),
            "estimated_capacity_ah": round(estimated_capacity, 2),
            "confidence": confidence,
        }
        self.stats.capacity_observations.append(observation)
        self.stats.capacity_observations = self.stats.capacity_observations[-MAX_CAPACITY_OBSERVATIONS:]
        self.stats.capacity_observation_count += 1
        self._recompute_learned_capacity(inputs.capacity_ah)

    def _record_model_performance(
        self,
        now: str,
        prediction: BatteryPrediction,
        event_state: BatteryEventState | None,
        model_predictions: dict[str, BatteryPrediction] | None,
    ) -> None:
        """Update model accuracy statistics at calibration anchors."""
        if not model_predictions or event_state is None or not event_state.calibration_anchor or prediction.soc_percent is None:
            return

        reference_soc = _reference_soc_from_anchor(prediction, event_state)
        observation_models: dict[str, dict[str, float | None]] = {}
        for model, model_prediction in model_predictions.items():
            if model_prediction.soc_percent is None:
                continue
            error = abs(model_prediction.soc_percent - reference_soc)
            stats = self.stats.model_error_stats.setdefault(model, {"count": 0, "mean_abs_error": 0.0, "last_error": 0.0})
            count = int(stats.get("count", 0)) + 1
            old_mean = float(stats.get("mean_abs_error", 0.0))
            new_mean = old_mean + (error - old_mean) / count
            stats["count"] = count
            stats["mean_abs_error"] = round(new_mean, 3)
            stats["last_error"] = round(error, 3)
            self.stats.model_accuracy[model] = round(_clamp(1.0 - (new_mean / 50.0), 0.05, 1.0), 3)
            observation_models[model] = {
                "soc_percent": model_prediction.soc_percent,
                "abs_error": round(error, 3),
            }

        if observation_models:
            self.stats.model_performance_observations.append(
                {
                    "timestamp": now,
                    "event_state": event_state.state,
                    "reference_soc": reference_soc,
                    "models": observation_models,
                }
            )
            self.stats.model_performance_observations = self.stats.model_performance_observations[-MAX_MODEL_PERFORMANCE_OBSERVATIONS:]

    def _recompute_learned_capacity(self, configured_capacity_ah: float) -> None:
        """Recompute learned capacity from retained observations."""
        observations = self.stats.capacity_observations
        if not observations:
            return
        weights = {"low": 0.25, "medium": 0.65, "high": 1.0}
        weighted_sum = 0.0
        total_weight = 0.0
        for observation in observations:
            capacity = observation.get("estimated_capacity_ah")
            try:
                capacity_f = float(capacity)
            except (TypeError, ValueError):
                continue
            weight = weights.get(str(observation.get("confidence", "low")), 0.25)
            weighted_sum += capacity_f * weight
            total_weight += weight
        if total_weight <= 0:
            return
        learned_capacity = weighted_sum / total_weight
        self.stats.learned_capacity_ah = round(learned_capacity, 2)
        self.stats.capacity_retention_percent = round(_clamp((learned_capacity / max(configured_capacity_ah, 0.1)) * 100.0, 0.0, 120.0), 1)
        if len(observations) >= 5 and any(obs.get("confidence") == "high" for obs in observations):
            self.stats.capacity_confidence = "high"
        elif len(observations) >= 2 or any(obs.get("confidence") == "medium" for obs in observations):
            self.stats.capacity_confidence = "medium"
        else:
            self.stats.capacity_confidence = "low"


def _reference_soc_from_anchor(prediction: BatteryPrediction, event_state: BatteryEventState) -> float:
    """Return an anchor-derived reference SOC for model accuracy learning."""
    if event_state.state in {"float", "absorption"}:
        return 100.0
    if event_state.state == "low_battery":
        return min(prediction.soc_percent or 20.0, 20.0)
    return float(prediction.soc_percent or 50.0)


def _running_average(current: float | None, value: float, count: int) -> float:
    """Return online running average."""
    if current is None or count <= 0:
        return value
    return current + (value - current) / (count + 1)


def _min_optional(current: float | None, value: float) -> float:
    return value if current is None else min(current, value)


def _max_optional(current: float | None, value: float) -> float:
    return value if current is None else max(current, value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
