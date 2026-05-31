"""Sensors for Battery Remaining Time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ALGORITHM,
    ATTR_BATTERY_BRAND_MODEL,
    ATTR_BATTERY_TYPE,
    ATTR_CONFIDENCE,
    ATTR_HISTORY_WINDOW_MINUTES,
    ATTR_MODE,
    ATTR_REASON,
    ATTR_SOC_PERCENT,
    BATTERY_TYPE_LABELS,
    CONF_BATTERY_BRAND_MODEL,
    CONF_BATTERY_TYPE,
    CONF_HISTORY_WINDOW_MINUTES,
    DEFAULT_BATTERY_BRAND_MODEL,
    DEFAULT_BATTERY_TYPE,
    DOMAIN,
)
from .coordinator import BatteryRemainingTimeCoordinator
from .predictor import BatteryPrediction


@dataclass(frozen=True, kw_only=True)
class BatterySensorDescription(SensorEntityDescription):
    """Battery forecast sensor description."""

    value_fn: Callable[[BatteryPrediction], Any]


@dataclass(frozen=True, kw_only=True)
class BatteryStatsSensorDescription(SensorEntityDescription):
    """Battery learned statistics sensor description."""

    value_fn: Callable[[Any], Any]


SENSORS: tuple[BatterySensorDescription, ...] = (
    BatterySensorDescription(
        key="estimated_soc",
        translation_key="estimated_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.soc_percent,
    ),
    BatterySensorDescription(
        key="time_to_empty",
        translation_key="time_to_empty",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_to_empty_h,
    ),
    BatterySensorDescription(
        key="time_to_full",
        translation_key="time_to_full",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_to_full_h,
    ),
    BatterySensorDescription(
        key="net_power",
        translation_key="net_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.net_power_w,
    ),
    BatterySensorDescription(key="mode", translation_key="mode", value_fn=lambda data: data.mode),
    BatterySensorDescription(key="confidence", translation_key="confidence", value_fn=lambda data: data.confidence),
    BatterySensorDescription(key="algorithm", translation_key="algorithm", value_fn=lambda data: data.algorithm),
)

HEALTH_SENSORS: tuple[BatteryStatsSensorDescription, ...] = (
    BatteryStatsSensorDescription(
        key="battery_health",
        translation_key="battery_health",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.battery_health_percent,
    ),
    BatteryStatsSensorDescription(
        key="battery_useful_life",
        translation_key="battery_useful_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.useful_life_percent,
    ),
    BatteryStatsSensorDescription(
        key="equivalent_cycles",
        translation_key="equivalent_cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda stats: round(stats.estimated_cycle_equivalents, 3),
    ),
    BatteryStatsSensorDescription(
        key="health_confidence",
        translation_key="health_confidence",
        value_fn=lambda stats: stats.health_confidence,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Battery Remaining Time sensors."""
    coordinator: BatteryRemainingTimeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [BatteryRemainingTimeSensor(coordinator, entry, description) for description in SENSORS]
    entities.extend(BatteryStatsSensor(coordinator, entry, description) for description in HEALTH_SENSORS)
    entities.append(BatteryPredictionHealthSensor(coordinator, entry))
    entities.append(BatteryCalibrationStatusSensor(coordinator, entry))
    async_add_entities(entities)


def _battery_profile_attrs(entry: ConfigEntry) -> dict[str, Any]:
    """Return configured battery identity/profile attributes."""
    battery_type = entry.data.get(CONF_BATTERY_TYPE, DEFAULT_BATTERY_TYPE)
    return {
        ATTR_BATTERY_TYPE: battery_type,
        "battery_type_label": BATTERY_TYPE_LABELS.get(battery_type, str(battery_type)),
        ATTR_BATTERY_BRAND_MODEL: entry.data.get(CONF_BATTERY_BRAND_MODEL, DEFAULT_BATTERY_BRAND_MODEL),
    }


def _model_summary(coordinator: BatteryRemainingTimeCoordinator) -> dict[str, float | str | None]:
    """Return compact per-model SOC telemetry for entity attributes."""
    return {
        algorithm: telemetry.get("soc_percent")
        for algorithm, telemetry in coordinator.model_telemetry.items()
    }


def _health_attrs(coordinator: BatteryRemainingTimeCoordinator) -> dict[str, Any]:
    """Return learned battery health attributes."""
    stats = coordinator.stats_store.stats
    return {
        "battery_health_percent": stats.battery_health_percent,
        "useful_life_percent": stats.useful_life_percent,
        "health_confidence": stats.health_confidence,
        "health_observation_count": stats.health_observation_count,
        "estimated_cycle_equivalents": round(stats.estimated_cycle_equivalents, 3),
        "cumulative_discharge_ah": round(stats.cumulative_discharge_ah, 3),
        "cumulative_charge_ah": round(stats.cumulative_charge_ah, 3),
        "last_health_observation": stats.last_health_observation,
    }


class BatteryRemainingTimeSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Battery remaining time sensor."""

    entity_description: BatterySensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry, description: BatterySensorDescription) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> Any:
        """Return native sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        data = self.coordinator.data
        if data is None:
            return {}
        event_state = self.coordinator.event_state
        return {
            ATTR_ALGORITHM: data.algorithm,
            ATTR_SOC_PERCENT: data.soc_percent,
            ATTR_MODE: data.mode,
            ATTR_CONFIDENCE: data.confidence,
            ATTR_REASON: data.reason,
            ATTR_HISTORY_WINDOW_MINUTES: self.coordinator.config_entry.data.get(CONF_HISTORY_WINDOW_MINUTES),
            "algorithm_spread": self.coordinator.algorithm_spread,
            **_battery_profile_attrs(self._entry),
            "event_state": event_state.state if event_state else None,
            "calibration_anchor": event_state.calibration_anchor if event_state else None,
        }


class BatteryStatsSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Learned battery health/statistics sensor."""

    entity_description: BatteryStatsSensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry, description: BatteryStatsSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> Any:
        stats = self.coordinator.stats_store.stats
        return self.entity_description.value_fn(stats)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            **_battery_profile_attrs(self._entry),
            **_health_attrs(self.coordinator),
            "algorithm_spread": self.coordinator.algorithm_spread,
            "model_outputs": _model_summary(self.coordinator),
        }


class BatteryPredictionHealthSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Operational health sensor for prediction quality."""

    _attr_has_entity_name = True
    _attr_translation_key = "prediction_health"

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_prediction_health"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if data is None:
            return None
        event_state = self.coordinator.event_state
        if data.confidence == "low":
            return "degraded"
        if event_state is not None and event_state.state == "unknown":
            return "limited"
        if self.coordinator.algorithm_spread is not None and self.coordinator.algorithm_spread > 20:
            return "divergent"
        return "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {}
        event_state = self.coordinator.event_state
        stats = self.coordinator.stats_store.stats
        return {
            "algorithm": data.algorithm,
            "confidence": data.confidence,
            "mode": data.mode,
            "selected_soc_percent": data.soc_percent,
            "algorithm_spread": self.coordinator.algorithm_spread,
            "model_outputs": _model_summary(self.coordinator),
            "model_telemetry": self.coordinator.model_telemetry,
            **_battery_profile_attrs(self._entry),
            **_health_attrs(self.coordinator),
            "event_state": event_state.state if event_state else None,
            "event_evidence": event_state.evidence if event_state else [],
            "calibration_anchor": event_state.calibration_anchor if event_state else False,
            "history_window_minutes": self.coordinator.config_entry.data.get(CONF_HISTORY_WINDOW_MINUTES),
            "update_count": stats.update_count,
            "last_seen": stats.last_seen,
            "reason": data.reason,
        }


class BatteryCalibrationStatusSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Calibration evidence readiness sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "calibration_status"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calibration_status"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int:
        stats = self.coordinator.stats_store.stats
        score = 0
        score += min(stats.rest_events, 10) * 3
        score += min(stats.float_events, 10) * 3
        score += min(stats.absorption_events, 10) * 2
        score += min(stats.low_battery_events, 5) * 4
        score += min(stats.calibration_anchor_events, 20)
        return min(score, 100)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stats = self.coordinator.stats_store.stats
        return {
            "readiness_percent": self.native_value,
            "algorithm_spread": self.coordinator.algorithm_spread,
            "model_outputs": _model_summary(self.coordinator),
            **_battery_profile_attrs(self._entry),
            **_health_attrs(self.coordinator),
            "update_count": stats.update_count,
            "calibration_anchor_events": stats.calibration_anchor_events,
            "rest_events": stats.rest_events,
            "float_events": stats.float_events,
            "absorption_events": stats.absorption_events,
            "low_battery_events": stats.low_battery_events,
            "heavy_discharge_events": stats.heavy_discharge_events,
            "lowest_soc_percent": stats.lowest_soc_percent,
            "highest_soc_percent": stats.highest_soc_percent,
            "lowest_voltage": stats.lowest_voltage,
            "highest_voltage": stats.highest_voltage,
            "highest_charge_current": stats.highest_charge_current,
            "highest_discharge_current": stats.highest_discharge_current,
            "first_seen": stats.first_seen,
            "last_seen": stats.last_seen,
            "event_counts": stats.event_counts,
        }


def _device_info(entry: ConfigEntry) -> dict[str, Any]:
    data = entry.data
    battery_type = data.get(CONF_BATTERY_TYPE, DEFAULT_BATTERY_TYPE)
    battery_model = data.get(CONF_BATTERY_BRAND_MODEL, DEFAULT_BATTERY_BRAND_MODEL)
    model = BATTERY_TYPE_LABELS.get(battery_type, "Lead Acid")
    if battery_model:
        model = f"{model} - {battery_model}"
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": entry.title,
        "manufacturer": "Sundeep Goel",
        "model": model,
    }
