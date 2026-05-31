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

    # Learned health / useful remaining life indicators. These are evidence-based
    # diagnostics, not lab-grade capacity certification.
    battery_health_percent: float | None = None
    useful_life_percent: float | None = None
    health_confidence: str = "low"
    health_observation_count: int = 0
    estimated_cycle_equivalents: float = 0.0
    cumulative_discharge_ah: float = 0.0
    cumulative_charge_ah: float = 0.0
    last_health_observation: dict[str, Any] = field(default_factory=dict)
    recent_health_observations: list[dict[str, Any]] = field(default_factory=list)

    # Capacity learning. Learned capacity is derived from anchor-to-anchor Ah
    # observations rather than set directly so bad samples can be inspected and
    # future algorithm changes can rebuild the result.
    configured_capacity_ah: float | None = None
    learned_capacity_ah: float | None = None
    capacity_retention_percent: float | None = None
    capacity_confidence: str = "low"
    capacity_observation_count: int = 0
    capacity_observations: list[dict[str, Any]] = field(default_factory=list)
    last_capacity_anchor: dict[str, Any] = field(default_factory=dict)

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
        self._record_capacity_observation(now, inputs, prediction, event_state)

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
        """Update learned health indicators from observed operating shape.

        This intentionally starts conservative. True remaining life requires many
        charge/discharge cycles. Until those are observed, confidence remains low.
        """
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

    def _record_capacity_observation(
        self,
        now: str,
        inputs: BatteryInputs,
        prediction: BatteryPrediction,
        event_state: BatteryEventState | None,
    ) -> None:
        """Learn usable capacity from anchor-to-anchor charge/discharge evidence."""
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
        self.stats.last_capacity_anchor = anchor
        if not previous:
            return

        try:
            previous_soc = float(previous.get("soc_percent"))
            previous_discharge_ah = float(previous.get("cumulative_discharge_ah", 0.0))
            previous_charge_ah = float(previous.get("cumulative_charge_ah", 0.0))
        except (TypeError, ValueError):
            return

        soc_delta = previous_soc - prediction.soc_percent
        discharged_ah = self.stats.cumulative_discharge_ah - previous_discharge_ah
        charged_ah = self.stats.cumulative_charge_ah - previous_charge_ah
        if soc_delta < 5.0 or discharged_ah <= 0:
            return

        estimated_capacity = discharged_ah / max(soc_delta / 100.0, 0.01)
        if estimated_capacity <= 0:
            return

        lower_bound = inputs.capacity_ah * 0.35
        upper_bound = inputs.capacity_ah * 1.20
        if not lower_bound <= estimated_capacity <= upper_bound:
            return

        confidence = "low"
        if soc_delta >= 10.0 and discharged_ah >= inputs.capacity_ah * 0.05:
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


def _min_optional(current: float | None, value: float) -> float:
    return value if current is None else min(current, value)


def _max_optional(current: float | None, value: float) -> float:
    return value if current is None else max(current, value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
