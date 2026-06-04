"""Persistent statistics storage for Battery Remaining Time."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import isfinite, log
from typing import Any

from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .events import BatteryEventState
from .predictor import BatteryInputs, BatteryPrediction, HistoryPoint, estimate_soc_ocv, practical_usable_soc

STORAGE_KEY = "battery_remaining_time"
STORAGE_VERSION = 1
MAX_HEALTH_OBSERVATIONS = 200
MAX_CAPACITY_OBSERVATIONS = 100
MAX_MODEL_PERFORMANCE_OBSERVATIONS = 200
MAX_ANCHOR_OBSERVATIONS = 200
MAX_PEUCKERT_OBSERVATIONS = 100
DEFAULT_PEUCKERT_EXPONENT = 1.20
MIN_PEUCKERT_EXPONENT = 1.00
MAX_PEUCKERT_EXPONENT = 1.60
DEFAULT_CHARGE_EFFICIENCY = 0.85


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
    last_history_point_timestamp: str | None = None

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
    learned_depletion_voltage: float | None = None
    depletion_voltage_confidence: str = "low"
    depletion_voltage_observation_count: int = 0
    depletion_voltage_observations: list[dict[str, Any]] = field(default_factory=list)
    learned_charge_efficiency: float | None = None
    charge_efficiency_confidence: str = "low"
    charge_efficiency_observation_count: int = 0
    anchor_observations: list[dict[str, Any]] = field(default_factory=list)

    model_error_stats: dict[str, dict[str, float | int]] = field(default_factory=dict)
    model_accuracy: dict[str, float] = field(default_factory=dict)
    model_performance_observations: list[dict[str, Any]] = field(default_factory=list)

    learned_peukert_exponent: float | None = None
    peukert_confidence: str = "low"
    peukert_observation_count: int = 0
    peukert_observations: list[dict[str, Any]] = field(default_factory=list)
    peukert_cycle: dict[str, Any] = field(default_factory=dict)

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

    def __init__(self, hass: Any, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
        self.stats = BatteryStats()

    async def async_load(self) -> None:
        """Load stored stats."""
        self.stats = BatteryStats.from_dict(await self._store.async_load())

    async def async_save(self) -> None:
        """Persist current stats."""
        await self._store.async_save(self.stats.as_dict())

    def effective_capacity_ah(self, configured_capacity_ah: float) -> float:
        """Return optimized capacity only when learning confidence is trusted."""
        learned_capacity = self.stats.learned_capacity_ah
        if self.stats.capacity_confidence == "low" or learned_capacity is None:
            return configured_capacity_ah
        return round(_clamp(learned_capacity, configured_capacity_ah * 0.35, configured_capacity_ah * 1.20), 2)

    def effective_charge_efficiency(self, configured_efficiency: float = DEFAULT_CHARGE_EFFICIENCY) -> float:
        """Return optimized charge efficiency only when learning confidence is trusted."""
        learned_efficiency = self.stats.learned_charge_efficiency
        if self.stats.charge_efficiency_confidence == "low" or learned_efficiency is None:
            return configured_efficiency
        return round(_clamp(learned_efficiency, 0.50, 1.05), 3)

    def effective_peukert_exponent(self, configured_exponent: float = DEFAULT_PEUCKERT_EXPONENT) -> float:
        """Return learned Peukert exponent only when enough observations exist."""
        if self.stats.peukert_confidence == "low" or self.stats.learned_peukert_exponent is None:
            return configured_exponent
        return _clamp(self.stats.learned_peukert_exponent, MIN_PEUCKERT_EXPONENT, MAX_PEUCKERT_EXPONENT)

    def effective_depletion_voltage(self, configured_voltage: float | None) -> float | None:
        """Return learned depletion voltage only when enough evidence exists."""
        learned_voltage = self.stats.learned_depletion_voltage
        if configured_voltage is None:
            return learned_voltage if self.stats.depletion_voltage_confidence != "low" else None
        if self.stats.depletion_voltage_confidence == "low" or learned_voltage is None:
            return configured_voltage
        lower = max(configured_voltage * 0.80, 1.0)
        upper = configured_voltage * 1.05
        return round(_clamp(learned_voltage, lower, upper), 2)

    def optimized_profile(self, configured_capacity_ah: float, configured_depletion_voltage: float | None = None) -> dict[str, Any]:
        """Return profile optimization details for diagnostics and logging."""
        effective_capacity = self.effective_capacity_ah(configured_capacity_ah)
        effective_efficiency = self.effective_charge_efficiency()
        effective_depletion_voltage = self.effective_depletion_voltage(configured_depletion_voltage)
        configured_capacity = max(configured_capacity_ah, 0.1)
        retention = self.stats.capacity_retention_percent
        if retention is None and self.stats.learned_capacity_ah is not None:
            retention = round((self.stats.learned_capacity_ah / configured_capacity) * 100.0, 1)

        ageing_rate = None
        if retention is not None and self.stats.estimated_cycle_equivalents > 0:
            ageing_rate = round(
                max(0.0, (100.0 - retention)) / max(self.stats.estimated_cycle_equivalents, 0.1) * 100.0,
                3,
            )

        return {
            "profile_optimization_active": (
                effective_capacity != round(configured_capacity_ah, 2)
                or effective_efficiency != round(DEFAULT_CHARGE_EFFICIENCY, 3)
            ),
            "effective_capacity_ah": effective_capacity,
            "effective_charge_efficiency": effective_efficiency,
            "effective_depletion_voltage": effective_depletion_voltage,
            "capacity_source": "learned" if effective_capacity != round(configured_capacity_ah, 2) else "configured",
            "charge_efficiency_source": "learned" if effective_efficiency != round(DEFAULT_CHARGE_EFFICIENCY, 3) else "configured",
            "depletion_voltage_source": "learned" if effective_depletion_voltage is not None and self.stats.depletion_voltage_confidence != "low" else "configured",
            "capacity_retention_percent": retention,
            "battery_ageing_rate_percent_per_100_cycles": ageing_rate,
        }

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

        new_history_points = _new_history_points(inputs.history, self.stats.last_history_point_timestamp)
        self._record_health_observation(now, inputs, prediction, event_state, new_history_points)
        self._record_peukert_observation(now, inputs, prediction, event_state, new_history_points)
        self._record_anchor_observation(now, inputs, prediction, event_state)
        self._record_capacity_observation(now, inputs, prediction, event_state)
        self._record_model_performance(now, inputs, event_state, model_predictions)
        latest_history_timestamp = _latest_history_timestamp(inputs.history)
        if latest_history_timestamp is not None:
            self.stats.last_history_point_timestamp = latest_history_timestamp.isoformat()

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
        history_points: list[HistoryPoint],
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

        for point in history_points:
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
            previous_soc = inputs.previous_soc_percent
            spread = abs(prediction.soc_percent - previous_soc) if previous_soc is not None else 0.0

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

    def _record_peukert_observation(
        self,
        now: str,
        inputs: BatteryInputs,
        prediction: BatteryPrediction,
        event_state: BatteryEventState | None,
        history_points: list[HistoryPoint],
    ) -> None:
        """Learn Peukert exponent from discharge windows ending at low battery."""
        if inputs.capacity_ah <= 0 or inputs.nominal_voltage <= 0:
            return

        segment = _discharge_segment(history_points, inputs) if len(history_points) >= 3 else None
        if segment is not None:
            self._update_peukert_cycle(segment)

        if event_state is None or not event_state.calibration_anchor or event_state.state != "low_battery":
            return

        cycle = self.stats.peukert_cycle
        if not cycle:
            return

        try:
            actual_runtime_h = float(cycle.get("runtime_h"))
            weighted_power_wh = float(cycle.get("weighted_power_wh"))
            weighted_current_ah = float(cycle.get("weighted_current_ah"))
            start_voltage = float(cycle.get("start_voltage"))
        except (TypeError, ValueError):
            self.stats.peukert_cycle = {}
            return

        average_power_w = weighted_power_wh / max(actual_runtime_h, 0.001)
        average_current_a = weighted_current_ah / max(actual_runtime_h, 0.001)
        if actual_runtime_h < 0.10 or average_power_w <= 1.0 or average_current_a <= 0.0:
            self.stats.peukert_cycle = {}
            return

        start_inputs = BatteryInputs(
            algorithm=inputs.algorithm,
            capacity_ah=inputs.capacity_ah,
            nominal_voltage=inputs.nominal_voltage,
            voltage=start_voltage,
            current=-average_current_a,
            discharge_power=average_power_w,
            temperature=cycle.get("start_temperature") if cycle.get("start_temperature") is not None else inputs.temperature,
            depletion_voltage=inputs.depletion_voltage,
            peukert_exponent=DEFAULT_PEUCKERT_EXPONENT,
        )
        start_soc = estimate_soc_ocv(start_voltage, inputs.nominal_voltage)
        usable_soc = practical_usable_soc(start_inputs, start_soc)
        if usable_soc is None or usable_soc <= 5.0:
            self.stats.peukert_cycle = {}
            return

        remaining_wh = inputs.capacity_ah * inputs.nominal_voltage * (usable_soc / 100.0)
        base_runtime_h = remaining_wh / average_power_w
        rated_current = max(inputs.capacity_ah / 20.0, 0.1)
        rate_ratio = rated_current / max(average_current_a, 0.1)
        if base_runtime_h <= 0 or rate_ratio <= 0 or abs(rate_ratio - 1.0) < 0.05:
            self.stats.peukert_cycle = {}
            return

        try:
            observed_exponent = 1.0 + (log(actual_runtime_h / base_runtime_h) / log(rate_ratio))
        except (ValueError, ZeroDivisionError):
            self.stats.peukert_cycle = {}
            return
        if not isfinite(observed_exponent):
            self.stats.peukert_cycle = {}
            return
        observed_exponent = _clamp(observed_exponent, MIN_PEUCKERT_EXPONENT, MAX_PEUCKERT_EXPONENT)

        configured_prediction_h = _peukert_runtime_hours(base_runtime_h, rate_ratio, DEFAULT_PEUCKERT_EXPONENT)
        learned_prediction_h = _peukert_runtime_hours(base_runtime_h, rate_ratio, observed_exponent)
        observation = {
            "timestamp": now,
            "event_state": event_state.state,
            "start_voltage": round(start_voltage, 4),
            "start_soc_percent": round(start_soc, 2) if start_soc is not None else None,
            "usable_soc_percent": round(usable_soc, 2),
            "actual_runtime_h": round(actual_runtime_h, 3),
            "configured_prediction_h": round(configured_prediction_h, 3),
            "learned_prediction_h": round(learned_prediction_h, 3),
            "average_discharge_power_w": round(average_power_w, 2),
            "average_discharge_current_a": round(average_current_a, 3),
            "observed_exponent": round(observed_exponent, 4),
            "selected_prediction_h": prediction.time_to_depletion_h or prediction.time_to_empty_h,
        }
        self.stats.peukert_observations.append(observation)
        self.stats.peukert_observations = self.stats.peukert_observations[-MAX_PEUCKERT_OBSERVATIONS:]
        self.stats.peukert_observation_count += 1
        self.stats.peukert_cycle = {}
        self._recompute_learned_peukert()

    def _update_peukert_cycle(self, segment: tuple[HistoryPoint, float, float, float]) -> None:
        """Accumulate an in-progress recorder discharge cycle."""
        start, runtime_h, average_power_w, average_current_a = segment
        if start.voltage is None:
            return
        cycle = self.stats.peukert_cycle
        if not cycle:
            cycle = {
                "start_voltage": start.voltage,
                "start_temperature": start.temperature,
                "runtime_h": 0.0,
                "weighted_power_wh": 0.0,
                "weighted_current_ah": 0.0,
            }
        cycle["runtime_h"] = float(cycle.get("runtime_h", 0.0)) + runtime_h
        cycle["weighted_power_wh"] = float(cycle.get("weighted_power_wh", 0.0)) + (average_power_w * runtime_h)
        cycle["weighted_current_ah"] = float(cycle.get("weighted_current_ah", 0.0)) + (average_current_a * runtime_h)
        self.stats.peukert_cycle = cycle

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

        if event_state.state in {"low_battery", "depletion_imminent"} and inputs.voltage is not None:
            learned_depletion = inputs.voltage
            self.stats.learned_depletion_voltage = _running_average(
                self.stats.learned_depletion_voltage,
                learned_depletion,
                self.stats.depletion_voltage_observation_count,
            )
            self.stats.depletion_voltage_observation_count += 1
            depletion_observation = {
                "timestamp": now,
                "event_state": event_state.state,
                "voltage": round(inputs.voltage, 4),
                "usable_soc": round(prediction.usable_soc_percent, 2) if prediction.usable_soc_percent is not None else None,
                "depletion_voltage": round(inputs.depletion_voltage, 4) if inputs.depletion_voltage is not None else None,
                "confidence": "medium" if self.stats.depletion_voltage_observation_count >= 3 else "low",
            }
            self.stats.depletion_voltage_observations.append(depletion_observation)
            self.stats.depletion_voltage_observations = self.stats.depletion_voltage_observations[-MAX_ANCHOR_OBSERVATIONS:]
            if self.stats.depletion_voltage_observation_count >= 8:
                self.stats.depletion_voltage_confidence = "high"
            elif self.stats.depletion_voltage_observation_count >= 3:
                self.stats.depletion_voltage_confidence = "medium"
            else:
                self.stats.depletion_voltage_confidence = "low"

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
        if inputs.depletion_voltage is not None:
            self.stats.last_capacity_anchor["depletion_voltage"] = inputs.depletion_voltage

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
        inputs: BatteryInputs,
        event_state: BatteryEventState | None,
        model_predictions: dict[str, BatteryPrediction] | None,
    ) -> None:
        """Update model accuracy statistics at calibration anchors."""
        if not model_predictions or event_state is None or not event_state.calibration_anchor:
            return

        reference_soc = _reference_soc_from_anchor(inputs, event_state)
        if reference_soc is None:
            return
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

    def _recompute_learned_peukert(self) -> None:
        """Recompute learned Peukert exponent from retained discharge observations."""
        observations = self.stats.peukert_observations
        if not observations:
            return

        weighted_sum = 0.0
        total_weight = 0.0
        for observation in observations:
            try:
                exponent = float(observation.get("observed_exponent"))
                actual = float(observation.get("actual_runtime_h"))
                power = float(observation.get("average_discharge_power_w"))
            except (TypeError, ValueError):
                continue
            if not isfinite(exponent):
                continue
            weight = _clamp(actual, 0.25, 4.0) * _clamp(power / 100.0, 0.5, 3.0)
            weighted_sum += exponent * weight
            total_weight += weight

        if total_weight <= 0:
            return

        previous = self.stats.learned_peukert_exponent
        learned = weighted_sum / total_weight
        if previous is not None and self.stats.peukert_observation_count > len(observations):
            learned = (previous * 0.75) + (learned * 0.25)
        self.stats.learned_peukert_exponent = round(_clamp(learned, MIN_PEUCKERT_EXPONENT, MAX_PEUCKERT_EXPONENT), 4)

        if self.stats.peukert_observation_count >= 8:
            self.stats.peukert_confidence = "high"
        elif self.stats.peukert_observation_count >= 3:
            self.stats.peukert_confidence = "medium"
        else:
            self.stats.peukert_confidence = "low"


def _reference_soc_from_anchor(inputs: BatteryInputs, event_state: BatteryEventState) -> float | None:
    """Return an anchor-derived reference SOC for model accuracy learning.

    The reference must come from raw sensor evidence rather than the selected
    prediction, otherwise the learner trains on its own output.
    """
    if event_state.state in {"float", "absorption"}:
        return 100.0
    if event_state.state == "low_battery":
        if inputs.depletion_voltage is not None and inputs.voltage is not None:
            return practical_low_soc_reference(inputs)
        return 20.0
    if inputs.voltage is None:
        return None
    ocv_soc = estimate_soc_from_inputs(inputs)
    return ocv_soc if ocv_soc is not None else 50.0


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


def estimate_soc_from_inputs(inputs: BatteryInputs) -> float | None:
    """Return a voltage-derived SOC reference for anchor learning."""
    if inputs.voltage is None:
        return None
    from .predictor import estimate_soc_ocv

    return estimate_soc_ocv(inputs.voltage, inputs.nominal_voltage)


def practical_low_soc_reference(inputs: BatteryInputs) -> float:
    """Return a conservative low-SOC reference from raw input evidence."""
    if inputs.voltage is None:
        return 20.0
    if inputs.depletion_voltage is None:
        return 20.0
    if inputs.voltage <= inputs.depletion_voltage:
        return 0.0
    span = max(inputs.nominal_voltage * (12.8 / 12.0) - inputs.depletion_voltage, 0.1)
    return _clamp(((inputs.voltage - inputs.depletion_voltage) / span) * 20.0, 0.0, 20.0)


def _discharge_segment(history_points: list[HistoryPoint], inputs: BatteryInputs) -> tuple[HistoryPoint, float, float, float] | None:
    """Return a sustained discharge segment as start point, runtime, watts, amps."""
    discharge_points: list[tuple[HistoryPoint, float, float]] = []
    for point in history_points:
        power_w, current_a = _point_discharge_power_current(point, inputs.nominal_voltage)
        if power_w is None or current_a is None or power_w <= 1.0 or current_a <= 0:
            if discharge_points:
                break
            continue
        discharge_points.append((point, power_w, current_a))

    if len(discharge_points) < 3:
        return None

    actual_runtime_h = sum(max(point.dt_hours, 0.0) for point, _, _ in discharge_points)
    if actual_runtime_h <= 0:
        return None

    weighted_power = sum(power_w * max(point.dt_hours, 0.0) for point, power_w, _ in discharge_points)
    weighted_current = sum(current_a * max(point.dt_hours, 0.0) for point, _, current_a in discharge_points)
    average_power_w = weighted_power / actual_runtime_h
    average_current_a = weighted_current / actual_runtime_h
    return discharge_points[0][0], actual_runtime_h, average_power_w, average_current_a


def _point_discharge_power_current(point: HistoryPoint, nominal_voltage: float) -> tuple[float | None, float | None]:
    """Return positive discharge power/current for one history point."""
    voltage = point.voltage if point.voltage is not None and point.voltage > 0 else nominal_voltage
    if point.current is not None and point.current < 0:
        current = abs(point.current)
        return current * voltage, current
    if point.discharge_power is not None and point.discharge_power > 0:
        return point.discharge_power, point.discharge_power / max(voltage, 0.1)
    return None, None


def _peukert_runtime_hours(base_runtime_h: float, rate_ratio: float, exponent: float) -> float:
    """Return runtime adjusted by Peukert exponent using existing predictor shape."""
    factor = rate_ratio ** max(exponent - 1.0, 0.0)
    return base_runtime_h * _clamp(factor, 0.25, 1.2)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return dt_util.parse_datetime(value)


def _latest_history_timestamp(history: list[HistoryPoint]) -> datetime | None:
    timestamps = [point.timestamp for point in history if point.timestamp is not None]
    if not timestamps:
        return None
    return max(timestamps)


def _new_history_points(history: list[HistoryPoint], last_processed_timestamp: str | None) -> list[HistoryPoint]:
    last_processed = _parse_timestamp(last_processed_timestamp)
    if last_processed is None:
        return history
    points = [point for point in history if point.timestamp is not None and point.timestamp > last_processed]
    return points
