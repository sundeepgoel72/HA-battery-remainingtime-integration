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
from homeassistant.util import slugify

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

UNIT_AMPERE_HOUR = "Ah"
UNIT_CYCLES = "cycles"
DEFAULT_EXPECTED_CYCLE_LIFE = 1200.0
EXPECTED_CYCLE_LIFE_BY_TYPE = {
    "flooded_lead_acid": 800.0,
    "tubular_lead_acid": 1500.0,
    "agm": 600.0,
    "gel": 800.0,
    "lead_carbon": 2000.0,
    "custom": DEFAULT_EXPECTED_CYCLE_LIFE,
}

MODEL_SOC_SENSOR_KEYS = (
    "voltage_only",
    "current_flow",
    "power_flow",
    "peukert",
    "hybrid_lead_acid",
    "temperature_compensated",
    "kibam",
    "shepherd",
    "adaptive_hybrid",
    "ensemble",
)

SENSOR_NAMES = {
    "estimated_soc": "Estimated SOC",
    "time_to_empty": "Time to empty",
    "time_to_full": "Time to full",
    "net_power": "Net power",
    "mode": "Mode",
    "confidence": "Confidence",
    "algorithm": "Algorithm",
    "battery_health": "Battery health",
    "battery_useful_life": "Battery useful life",
    "equivalent_cycles": "Equivalent cycles",
    "health_confidence": "Health confidence",
    "learned_capacity": "Learned capacity",
    "capacity_retention": "Capacity retention",
    "capacity_confidence": "Capacity confidence",
    "remaining_cycles": "Remaining cycles",
    "remaining_life": "Remaining life",
    "algorithm_spread": "Algorithm spread",
    "prediction_health": "Prediction health",
    "calibration_status": "Calibration status",
}

MODEL_SENSOR_NAMES = {
    "voltage_only": "SOC voltage only",
    "current_flow": "SOC current flow",
    "power_flow": "SOC power flow",
    "peukert": "SOC Peukert",
    "hybrid_lead_acid": "SOC hybrid lead acid",
    "temperature_compensated": "SOC temperature compensated",
    "kibam": "SOC KiBaM",
    "shepherd": "SOC Shepherd",
    "adaptive_hybrid": "SOC adaptive hybrid",
    "ensemble": "SOC ensemble",
}


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
        name=SENSOR_NAMES["estimated_soc"],
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.soc_percent,
    ),
    BatterySensorDescription(
        key="time_to_empty",
        name=SENSOR_NAMES["time_to_empty"],
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_to_empty_h,
    ),
    BatterySensorDescription(
        key="time_to_full",
        name=SENSOR_NAMES["time_to_full"],
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_to_full_h,
    ),
    BatterySensorDescription(
        key="net_power",
        name=SENSOR_NAMES["net_power"],
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.net_power_w,
    ),
    BatterySensorDescription(key="mode", name=SENSOR_NAMES["mode"], value_fn=lambda data: data.mode),
    BatterySensorDescription(key="confidence", name=SENSOR_NAMES["confidence"], value_fn=lambda data: data.confidence),
    BatterySensorDescription(key="algorithm", name=SENSOR_NAMES["algorithm"], value_fn=lambda data: data.algorithm),
)

HEALTH_SENSORS: tuple[BatteryStatsSensorDescription, ...] = (
    BatteryStatsSensorDescription(
        key="battery_health",
        name=SENSOR_NAMES["battery_health"],
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.battery_health_percent,
    ),
    BatteryStatsSensorDescription(
        key="battery_useful_life",
        name=SENSOR_NAMES["battery_useful_life"],
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.useful_life_percent,
    ),
    BatteryStatsSensorDescription(
        key="equivalent_cycles",
        name=SENSOR_NAMES["equivalent_cycles"],
        native_unit_of_measurement=UNIT_CYCLES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda stats: round(stats.estimated_cycle_equivalents, 3),
    ),
    BatteryStatsSensorDescription(
        key="health_confidence",
        name=SENSOR_NAMES["health_confidence"],
        value_fn=lambda stats: stats.health_confidence,
    ),
    BatteryStatsSensorDescription(
        key="learned_capacity",
        name=SENSOR_NAMES["learned_capacity"],
        native_unit_of_measurement=UNIT_AMPERE_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.learned_capacity_ah,
    ),
    BatteryStatsSensorDescription(
        key="capacity_retention",
        name=SENSOR_NAMES["capacity_retention"],
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: stats.capacity_retention_percent,
    ),
    BatteryStatsSensorDescription(
        key="capacity_confidence",
        name=SENSOR_NAMES["capacity_confidence"],
        value_fn=lambda stats: stats.capacity_confidence,
    ),
    BatteryStatsSensorDescription(
        key="remaining_cycles",
        name=SENSOR_NAMES["remaining_cycles"],
        native_unit_of_measurement=UNIT_CYCLES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: None,
    ),
    BatteryStatsSensorDescription(
        key="remaining_life",
        name=SENSOR_NAMES["remaining_life"],
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: None,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Battery Remaining Time sensors."""
    coordinator: BatteryRemainingTimeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [BatteryRemainingTimeSensor(coordinator, entry, description) for description in SENSORS]
    entities.extend(BatteryStatsSensor(coordinator, entry, description) for description in HEALTH_SENSORS)
    entities.extend(BatteryModelSocSensor(coordinator, entry, model_key) for model_key in MODEL_SOC_SENSOR_KEYS)
    entities.append(BatteryAlgorithmSpreadSensor(coordinator, entry))
    entities.append(BatteryPredictionHealthSensor(coordinator, entry))
    entities.append(BatteryCalibrationStatusSensor(coordinator, entry))
    async_add_entities(entities)


def _object_id(entry: ConfigEntry, key: str) -> str:
    """Return stable suggested entity object id for new registry entries."""
    base = slugify(entry.title or "battery") or "battery"
    return f"{base}_{key}"


def _battery_profile_attrs(entry: ConfigEntry) -> dict[str, Any]:
    """Return configured battery identity/profile attributes."""
    battery_type = entry.data.get(CONF_BATTERY_TYPE, DEFAULT_BATTERY_TYPE)
    return {
        ATTR_BATTERY_TYPE: battery_type,
        "battery_type_label": BATTERY_TYPE_LABELS.get(battery_type, str(battery_type)),
        ATTR_BATTERY_BRAND_MODEL: entry.data.get(CONF_BATTERY_BRAND_MODEL, DEFAULT_BATTERY_BRAND_MODEL),
    }


def _expected_cycle_life(entry: ConfigEntry) -> float:
    """Return default expected cycle life for configured battery type."""
    battery_type = str(entry.data.get(CONF_BATTERY_TYPE, DEFAULT_BATTERY_TYPE))
    return EXPECTED_CYCLE_LIFE_BY_TYPE.get(battery_type, DEFAULT_EXPECTED_CYCLE_LIFE)


def _remaining_cycles(coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> float | None:
    """Estimate remaining useful cycle count from configured type and observed equivalent cycles."""
    stats = coordinator.stats_store.stats
    expected = _expected_cycle_life(entry)
    if expected <= 0:
        return None
    return round(max(expected - stats.estimated_cycle_equivalents, 0.0), 1)


def _remaining_life_percent(coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> float | None:
    """Estimate remaining useful life percent from cycle life and capacity retention."""
    stats = coordinator.stats_store.stats
    expected = _expected_cycle_life(entry)
    if expected <= 0:
        return None
    cycle_life = max(0.0, min(100.0, ((expected - stats.estimated_cycle_equivalents) / expected) * 100.0))
    if stats.capacity_retention_percent is None:
        return round(cycle_life, 1)
    return round(min(cycle_life, stats.capacity_retention_percent), 1)


def _model_summary(coordinator: BatteryRemainingTimeCoordinator) -> dict[str, float | str | None]:
    """Return compact per-model SOC telemetry for entity attributes."""
    return {algorithm: telemetry.get("soc_percent") for algorithm, telemetry in coordinator.model_telemetry.items()}


def _health_attrs(coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> dict[str, Any]:
    """Return learned battery health attributes."""
    stats = coordinator.stats_store.stats
    return {
        "battery_health_percent": stats.battery_health_percent,
        "useful_life_percent": stats.useful_life_percent,
        "health_confidence": stats.health_confidence,
        "health_observation_count": stats.health_observation_count,
        "configured_capacity_ah": stats.configured_capacity_ah,
        "learned_capacity_ah": stats.learned_capacity_ah,
        "capacity_retention_percent": stats.capacity_retention_percent,
        "capacity_confidence": stats.capacity_confidence,
        "capacity_observation_count": stats.capacity_observation_count,
        "estimated_cycle_equivalents": round(stats.estimated_cycle_equivalents, 3),
        "expected_cycle_life": _expected_cycle_life(entry),
        "remaining_cycles": _remaining_cycles(coordinator, entry),
        "remaining_life_percent": _remaining_life_percent(coordinator, entry),
        "cumulative_discharge_ah": round(stats.cumulative_discharge_ah, 3),
        "cumulative_charge_ah": round(stats.cumulative_charge_ah, 3),
        "last_capacity_anchor": stats.last_capacity_anchor,
        "last_capacity_observation": stats.capacity_observations[-1] if stats.capacity_observations else None,
        "last_health_observation": stats.last_health_observation,
    }


class BatteryRemainingTimeSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Battery remaining time sensor."""

    entity_description: BatterySensorDescription
    _attr_has_entity_name = False

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry, description: BatterySensorDescription) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_name = str(description.name or description.key)
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_suggested_object_id = _object_id(entry, description.key)
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
    _attr_has_entity_name = False

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry, description: BatteryStatsSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_name = str(description.name or description.key)
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_suggested_object_id = _object_id(entry, description.key)
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> Any:
        stats = self.coordinator.stats_store.stats
        if self.entity_description.key == "remaining_cycles":
            return _remaining_cycles(self.coordinator, self._entry)
        if self.entity_description.key == "remaining_life":
            return _remaining_life_percent(self.coordinator, self._entry)
        return self.entity_description.value_fn(stats)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            **_battery_profile_attrs(self._entry),
            **_health_attrs(self.coordinator, self._entry),
            "algorithm_spread": self.coordinator.algorithm_spread,
            "model_outputs": _model_summary(self.coordinator),
        }


class BatteryModelSocSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Dedicated per-model SOC comparison sensor."""

    _attr_has_entity_name = False
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.BATTERY

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry, model_key: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._model_key = model_key
        self._attr_name = MODEL_SENSOR_NAMES.get(model_key, f"SOC {model_key}")
        self._attr_unique_id = f"{entry.entry_id}_soc_{model_key}"
        self._attr_suggested_object_id = _object_id(entry, f"soc_{model_key}")
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | str | None:
        return self.coordinator.model_telemetry.get(self._model_key, {}).get("soc_percent")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        telemetry = self.coordinator.model_telemetry.get(self._model_key, {})
        selected = self.coordinator.data
        return {
            "model": self._model_key,
            "model_telemetry": telemetry,
            "algorithm_spread": self.coordinator.algorithm_spread,
            "selected_algorithm": selected.algorithm if selected else None,
            "selected_soc_percent": selected.soc_percent if selected else None,
            **_battery_profile_attrs(self._entry),
        }


class BatteryAlgorithmSpreadSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Dedicated algorithm divergence/spread sensor."""

    _attr_has_entity_name = False
    _attr_name = SENSOR_NAMES["algorithm_spread"]
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_algorithm_spread"
        self._attr_suggested_object_id = _object_id(entry, "algorithm_spread")
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.algorithm_spread

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        selected = self.coordinator.data
        return {
            "model_outputs": _model_summary(self.coordinator),
            "selected_algorithm": selected.algorithm if selected else None,
            "selected_soc_percent": selected.soc_percent if selected else None,
            **_battery_profile_attrs(self._entry),
        }


class BatteryPredictionHealthSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Operational health sensor for prediction quality."""

    _attr_has_entity_name = False
    _attr_name = SENSOR_NAMES["prediction_health"]

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_prediction_health"
        self._attr_suggested_object_id = _object_id(entry, "prediction_health")
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
            "model_accuracy": stats.model_accuracy,
            "model_error_stats": stats.model_error_stats,
            **_battery_profile_attrs(self._entry),
            **_health_attrs(self.coordinator, self._entry),
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

    _attr_has_entity_name = False
    _attr_name = SENSOR_NAMES["calibration_status"]
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calibration_status"
        self._attr_suggested_object_id = _object_id(entry, "calibration_status")
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
            "model_accuracy": stats.model_accuracy,
            **_battery_profile_attrs(self._entry),
            **_health_attrs(self.coordinator, self._entry),
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
