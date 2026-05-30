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


def _min_optional(current: float | None, value: float) -> float:
    return value if current is None else min(current, value)


def _max_optional(current: float | None, value: float) -> float:
    return value if current is None else max(current, value)
