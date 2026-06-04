"""Sensors for Battery Remaining Time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTime
from homeassistant.helpers.entity import EntityCategory
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
    BATTERY_TYPE_AGM,
    BATTERY_TYPE_CUSTOM,
    BATTERY_TYPE_FLOODED,
    BATTERY_TYPE_GEL,
    BATTERY_TYPE_LEAD_CARBON,
    BATTERY_TYPE_TUBULAR,
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
from .runtime import runtime_config

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

UNIT_AMPERE_HOUR = "Ah"
UNIT_CYCLES = "cycles"
UNIT_VOLT = "V"
DEFAULT_EXPECTED_CYCLE_LIFE = 1200.0
EXPECTED_CYCLE_LIFE_BY_TYPE = {
    BATTERY_TYPE_FLOODED: 800.0,
    BATTERY_TYPE_TUBULAR: 1500.0,
    BATTERY_TYPE_AGM: 600.0,
    BATTERY_TYPE_GEL: 800.0,
    BATTERY_TYPE_LEAD_CARBON: 2000.0,
    BATTERY_TYPE_CUSTOM: DEFAULT_EXPECTED_CYCLE_LIFE,
}

SENSOR_NAMES = {
    "estimated_soc": "Estimated SOC",
    "time_to_empty": "Time to empty",
    "time_to_full": "Time to full",
    "usable_soc": "Usable SOC",
    "time_to_depletion": "Time to depletion",
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
    "learned_full_voltage": "Learned full voltage",
    "learned_empty_voltage": "Learned empty voltage",
    "configured_depletion_voltage": "Configured depletion voltage",
    "learned_depletion_voltage": "Learned depletion voltage",
    "depletion_voltage_confidence": "Depletion voltage confidence",
    "learned_charge_efficiency": "Learned charge efficiency",
    "learned_peukert_exponent": "Learned Peukert exponent",
    "peukert_confidence": "Peukert confidence",
    "peukert_observation_count": "Peukert observation count",
    "remaining_cycles": "Remaining cycles",
    "remaining_life": "Remaining life",
    "algorithm_spread": "Algorithm spread",
    "model_accuracy": "Model accuracy",
    "prediction_confidence": "Prediction confidence",
    "active_algorithm": "Active algorithm",
    "prediction_health": "Prediction health",
    "calibration_status": "Calibration status",
    "soc_ocv": "SOC OCV",
    "soc_coulomb": "SOC Coulomb",
    "soc_peukert": "SOC Peukert",
    "soc_hybrid": "SOC Hybrid",
    "soc_ensemble": "SOC Ensemble",
    "tte_ocv": "TTE OCV",
    "tte_coulomb": "TTE Coulomb",
    "tte_peukert": "TTE Peukert",
    "tte_hybrid": "TTE Hybrid",
    "tte_ensemble": "TTE Ensemble",
    "ttf_ocv": "TTF OCV",
    "ttf_coulomb": "TTF Coulomb",
    "ttf_peukert": "TTF Peukert",
    "ttf_hybrid": "TTF Hybrid",
    "ttf_ensemble": "TTF Ensemble",
}


@dataclass(frozen=True, kw_only=True)
class BatterySensorDescription(SensorEntityDescription):
    """Battery forecast sensor description."""

    value_fn: Callable[[BatteryPrediction], Any]


@dataclass(frozen=True, kw_only=True)
class BatteryStatsSensorDescription(SensorEntityDescription):
    """Battery learned statistics sensor description."""

    value_fn: Callable[[Any], Any]


@dataclass(frozen=True, kw_only=True)
class BatteryComparisonSensorDescription(SensorEntityDescription):
    """Per-algorithm comparison sensor description."""

    algorithm: str
    metric: str


@dataclass(frozen=True, kw_only=True)
class BatteryDiagnosticAliasSensorDescription(SensorEntityDescription):
    """Diagnostic alias sensor description."""

    value_fn: Callable[[BatteryRemainingTimeCoordinator], Any]


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
        key="usable_soc",
        name=SENSOR_NAMES["usable_soc"],
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.usable_soc_percent,
    ),
    BatterySensorDescription(
        key="time_to_depletion",
        name=SENSOR_NAMES["time_to_depletion"],
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.time_to_depletion_h,
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
        key="learned_full_voltage",
        name=SENSOR_NAMES["learned_full_voltage"],
        native_unit_of_measurement=UNIT_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: round(stats.learned_full_voltage, 3) if getattr(stats, "learned_full_voltage", None) is not None else None,
    ),
    BatteryStatsSensorDescription(
        key="learned_empty_voltage",
        name=SENSOR_NAMES["learned_empty_voltage"],
        native_unit_of_measurement=UNIT_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: round(stats.learned_empty_voltage, 3) if getattr(stats, "learned_empty_voltage", None) is not None else None,
    ),
    BatteryStatsSensorDescription(
        key="configured_depletion_voltage",
        name=SENSOR_NAMES["configured_depletion_voltage"],
        native_unit_of_measurement=UNIT_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: getattr(stats, "configured_depletion_voltage", None),
    ),
    BatteryStatsSensorDescription(
        key="learned_depletion_voltage",
        name=SENSOR_NAMES["learned_depletion_voltage"],
        native_unit_of_measurement=UNIT_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: round(stats.learned_depletion_voltage, 3) if getattr(stats, "learned_depletion_voltage", None) is not None else None,
    ),
    BatteryStatsSensorDescription(
        key="depletion_voltage_confidence",
        name=SENSOR_NAMES["depletion_voltage_confidence"],
        value_fn=lambda stats: getattr(stats, "depletion_voltage_confidence", "low"),
    ),
    BatteryStatsSensorDescription(
        key="learned_charge_efficiency",
        name=SENSOR_NAMES["learned_charge_efficiency"],
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: round(stats.learned_charge_efficiency * 100.0, 1) if getattr(stats, "learned_charge_efficiency", None) is not None else None,
    ),
    BatteryStatsSensorDescription(
        key="learned_peukert_exponent",
        name=SENSOR_NAMES["learned_peukert_exponent"],
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda stats: round(stats.learned_peukert_exponent, 4) if getattr(stats, "learned_peukert_exponent", None) is not None else None,
    ),
    BatteryStatsSensorDescription(
        key="peukert_confidence",
        name=SENSOR_NAMES["peukert_confidence"],
        value_fn=lambda stats: stats.peukert_confidence,
    ),
    BatteryStatsSensorDescription(
        key="peukert_observation_count",
        name=SENSOR_NAMES["peukert_observation_count"],
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda stats: stats.peukert_observation_count,
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

COMPARISON_SENSORS: tuple[BatteryComparisonSensorDescription, ...] = (
    BatteryComparisonSensorDescription(key="soc_ocv", name=SENSOR_NAMES["soc_ocv"], native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, algorithm="voltage_only", metric="soc_percent"),
    BatteryComparisonSensorDescription(key="soc_coulomb", name=SENSOR_NAMES["soc_coulomb"], native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, algorithm="current_flow", metric="soc_percent"),
    BatteryComparisonSensorDescription(key="soc_peukert", name=SENSOR_NAMES["soc_peukert"], native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, algorithm="peukert", metric="soc_percent"),
    BatteryComparisonSensorDescription(key="soc_hybrid", name=SENSOR_NAMES["soc_hybrid"], native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, algorithm="hybrid_lead_acid", metric="soc_percent"),
    BatteryComparisonSensorDescription(key="soc_ensemble", name=SENSOR_NAMES["soc_ensemble"], native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, algorithm="ensemble", metric="soc_percent"),
    BatteryComparisonSensorDescription(key="tte_ocv", name=SENSOR_NAMES["tte_ocv"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="voltage_only", metric="time_to_empty_h"),
    BatteryComparisonSensorDescription(key="tte_coulomb", name=SENSOR_NAMES["tte_coulomb"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="current_flow", metric="time_to_empty_h"),
    BatteryComparisonSensorDescription(key="tte_peukert", name=SENSOR_NAMES["tte_peukert"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="peukert", metric="time_to_empty_h"),
    BatteryComparisonSensorDescription(key="tte_hybrid", name=SENSOR_NAMES["tte_hybrid"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="hybrid_lead_acid", metric="time_to_empty_h"),
    BatteryComparisonSensorDescription(key="tte_ensemble", name=SENSOR_NAMES["tte_ensemble"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="ensemble", metric="time_to_empty_h"),
    BatteryComparisonSensorDescription(key="ttf_ocv", name=SENSOR_NAMES["ttf_ocv"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="voltage_only", metric="time_to_full_h"),
    BatteryComparisonSensorDescription(key="ttf_coulomb", name=SENSOR_NAMES["ttf_coulomb"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="current_flow", metric="time_to_full_h"),
    BatteryComparisonSensorDescription(key="ttf_peukert", name=SENSOR_NAMES["ttf_peukert"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="peukert", metric="time_to_full_h"),
    BatteryComparisonSensorDescription(key="ttf_hybrid", name=SENSOR_NAMES["ttf_hybrid"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="hybrid_lead_acid", metric="time_to_full_h"),
    BatteryComparisonSensorDescription(key="ttf_ensemble", name=SENSOR_NAMES["ttf_ensemble"], native_unit_of_measurement=UnitOfTime.HOURS, device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, algorithm="ensemble", metric="time_to_full_h"),
)

DIAGNOSTIC_ALIAS_SENSORS: tuple[BatteryDiagnosticAliasSensorDescription, ...] = (
    BatteryDiagnosticAliasSensorDescription(key="prediction_confidence", name=SENSOR_NAMES["prediction_confidence"], value_fn=lambda coordinator: coordinator.data.confidence if coordinator.data else None),
    BatteryDiagnosticAliasSensorDescription(key="active_algorithm", name=SENSOR_NAMES["active_algorithm"], value_fn=lambda coordinator: coordinator.data.algorithm if coordinator.data else None),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Battery Remaining Time sensors."""
    coordinator: BatteryRemainingTimeCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [BatteryRemainingTimeSensor(coordinator, entry, description) for description in SENSORS]
    entities.extend(BatteryStatsSensor(coordinator, entry, description) for description in HEALTH_SENSORS)
    entities.extend(BatteryComparisonSensor(coordinator, entry, description) for description in COMPARISON_SENSORS)
    entities.extend(BatteryDiagnosticAliasSensor(coordinator, entry, description) for description in DIAGNOSTIC_ALIAS_SENSORS)
    entities.append(BatteryAlgorithmSpreadSensor(coordinator, entry))
    entities.append(BatteryModelAccuracySensor(coordinator, entry))
    entities.append(BatteryPredictionHealthSensor(coordinator, entry))
    entities.append(BatteryCalibrationStatusSensor(coordinator, entry))
    async_add_entities(entities)


def _object_id(entry: ConfigEntry, key: str) -> str:
    """Return stable suggested entity object id for new registry entries."""
    base = slugify(entry.title or "battery") or "battery"
    return f"{base}_{key}"


def _battery_profile_attrs(entry: ConfigEntry) -> dict[str, Any]:
    """Return configured battery identity/profile attributes."""
    data = runtime_config(entry)
    battery_type = data.get(CONF_BATTERY_TYPE, DEFAULT_BATTERY_TYPE)
    return {
        ATTR_BATTERY_TYPE: battery_type,
        "battery_type_label": BATTERY_TYPE_LABELS.get(battery_type, str(battery_type)),
        ATTR_BATTERY_BRAND_MODEL: data.get(CONF_BATTERY_BRAND_MODEL, DEFAULT_BATTERY_BRAND_MODEL),
    }


def _expected_cycle_life(entry: ConfigEntry) -> float:
    """Return default expected cycle life for configured battery type."""
    battery_type = str(runtime_config(entry).get(CONF_BATTERY_TYPE, DEFAULT_BATTERY_TYPE))
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


def _model_soc_values(coordinator: BatteryRemainingTimeCoordinator) -> dict[str, float]:
    """Return numeric per-model SOC values excluding the ensemble itself."""
    values: dict[str, float] = {}
    for algorithm, telemetry in coordinator.model_telemetry.items():
        if algorithm == "ensemble":
            continue
        value = telemetry.get("soc_percent")
        if isinstance(value, (int, float)):
            values[algorithm] = float(value)
    return values


def _algorithm_stddev(coordinator: BatteryRemainingTimeCoordinator) -> float | None:
    """Return SOC standard deviation across non-ensemble models."""
    values = list(_model_soc_values(coordinator).values())
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return round(variance ** 0.5, 2)


def _algorithm_outlier(coordinator: BatteryRemainingTimeCoordinator) -> str | None:
    """Return the model furthest from the non-ensemble median when materially divergent."""
    values = _model_soc_values(coordinator)
    if len(values) < 3:
        return None
    sorted_values = sorted(values.values())
    mid = len(sorted_values) // 2
    median = sorted_values[mid] if len(sorted_values) % 2 else (sorted_values[mid - 1] + sorted_values[mid]) / 2
    model, distance = max(((model, abs(value - median)) for model, value in values.items()), key=lambda item: item[1])
    return model if distance >= 5.0 else None


def _model_accuracy_summary(coordinator: BatteryRemainingTimeCoordinator) -> dict[str, Any]:
    """Return a compact summary of learned model accuracy."""
    stats = coordinator.stats_store.stats
    accuracy = stats.model_accuracy
    if not accuracy:
        return {
            "average_accuracy": None,
            "best_model": None,
            "worst_model": None,
            "learned_model_count": 0,
            "model_accuracy": {},
        }

    learned = {model: float(value) for model, value in accuracy.items() if isinstance(value, (int, float))}
    average_accuracy = round(sum(learned.values()) / len(learned), 3) if learned else None
    best_model = max(learned, key=learned.get) if learned else None
    worst_model = min(learned, key=learned.get) if learned else None
    return {
        "average_accuracy": average_accuracy,
        "best_model": best_model,
        "worst_model": worst_model,
        "learned_model_count": len(learned),
        "model_accuracy": learned,
    }


def _confidence_score(coordinator: BatteryRemainingTimeCoordinator) -> int | None:
    """Return a 0-100 operational confidence score."""
    data = coordinator.data
    if data is None:
        return None
    score = {"high": 82.0, "medium": 62.0, "low": 35.0, "very_low": 12.0}.get(str(data.confidence), 50.0)
    spread = coordinator.algorithm_spread
    if spread is not None:
        if spread <= 2:
            score += 12
        elif spread <= 5:
            score += 8
        elif spread <= 10:
            score += 2
        elif spread <= 20:
            score -= 12
        else:
            score -= 30
    event_state = coordinator.event_state
    if event_state is not None:
        if event_state.calibration_anchor:
            score += 6
        if event_state.state == "unknown":
            score -= 20
    stats = coordinator.stats_store.stats
    if stats.calibration_anchor_events >= 50:
        score += 6
    elif stats.calibration_anchor_events >= 10:
        score += 3
    if stats.update_count < 5:
        score -= 15
    return int(max(0, min(100, round(score))))


def _health_attrs(coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> dict[str, Any]:
    """Return learned battery health attributes."""
    stats = coordinator.stats_store.stats
    profile = coordinator.stats_store.optimized_profile(stats.configured_capacity_ah or 0.0)
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
        "learned_full_voltage": getattr(stats, "learned_full_voltage", None),
        "learned_empty_voltage": getattr(stats, "learned_empty_voltage", None),
        "full_voltage_observation_count": getattr(stats, "full_voltage_observation_count", 0),
        "empty_voltage_observation_count": getattr(stats, "empty_voltage_observation_count", 0),
        "learned_charge_efficiency": getattr(stats, "learned_charge_efficiency", None),
        "charge_efficiency_confidence": getattr(stats, "charge_efficiency_confidence", "low"),
        "charge_efficiency_observation_count": getattr(stats, "charge_efficiency_observation_count", 0),
        "learned_peukert_exponent": getattr(stats, "learned_peukert_exponent", None),
        "peukert_confidence": getattr(stats, "peukert_confidence", "low"),
        "peukert_observation_count": getattr(stats, "peukert_observation_count", 0),
        "estimated_cycle_equivalents": round(stats.estimated_cycle_equivalents, 3),
        "expected_cycle_life": _expected_cycle_life(entry),
        "remaining_cycles": _remaining_cycles(coordinator, entry),
        "remaining_life_percent": _remaining_life_percent(coordinator, entry),
        "profile_optimization_active": profile["profile_optimization_active"],
        "effective_capacity_ah": profile["effective_capacity_ah"],
        "capacity_source": profile["capacity_source"],
        "effective_charge_efficiency": profile["effective_charge_efficiency"],
        "charge_efficiency_source": profile["charge_efficiency_source"],
        "battery_ageing_rate_percent_per_100_cycles": profile["battery_ageing_rate_percent_per_100_cycles"],
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
            ATTR_HISTORY_WINDOW_MINUTES: runtime_config(self.coordinator.config_entry).get(CONF_HISTORY_WINDOW_MINUTES),
            **_battery_profile_attrs(self._entry),
            "event_state": event_state.state if event_state else None,
            "calibration_anchor": event_state.calibration_anchor if event_state else None,
            "source_evidence_status": self.coordinator.source_evidence_status,
        }


class BatteryComparisonSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Per-algorithm comparison sensor for observability."""

    entity_description: BatteryComparisonSensorDescription
    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry, description: BatteryComparisonSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_name = str(description.name or description.key)
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_suggested_object_id = _object_id(entry, description.key)
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> Any:
        prediction = self.coordinator.model_predictions.get(self.entity_description.algorithm)
        if prediction is None:
            return None
        return getattr(prediction, self.entity_description.metric, None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        prediction = self.coordinator.model_predictions.get(self.entity_description.algorithm)
        if prediction is None:
            return {}
        return {
            "algorithm": prediction.algorithm,
            "confidence": prediction.confidence,
            "reason": prediction.reason,
            "mode": prediction.mode,
            "algorithm_spread": self.coordinator.algorithm_spread,
            "active_algorithm": self.coordinator.data.algorithm if self.coordinator.data else None,
            "source_evidence_status": self.coordinator.source_evidence_status,
            **_battery_profile_attrs(self._entry),
        }


class BatteryDiagnosticAliasSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Diagnostic alias sensor for requested observability keys."""

    entity_description: BatteryDiagnosticAliasSensorDescription
    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry, description: BatteryDiagnosticAliasSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_name = str(description.name or description.key)
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_suggested_object_id = _object_id(entry, description.key)
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "algorithm_spread": self.coordinator.algorithm_spread,
            "source_evidence_status": self.coordinator.source_evidence_status,
            **_battery_profile_attrs(self._entry),
        }


class BatteryStatsSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Learned battery health/statistics sensor."""

    entity_description: BatteryStatsSensorDescription
    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
        profile = self.coordinator.stats_store.optimized_profile(
            self.coordinator.stats_store.stats.configured_capacity_ah or 0.0
        )
        return {
            **_battery_profile_attrs(self._entry),
            "health_confidence": self.coordinator.stats_store.stats.health_confidence,
            "capacity_confidence": self.coordinator.stats_store.stats.capacity_confidence,
            "depletion_voltage_confidence": self.coordinator.stats_store.stats.depletion_voltage_confidence,
            "peukert_confidence": self.coordinator.stats_store.stats.peukert_confidence,
            "health_observation_count": self.coordinator.stats_store.stats.health_observation_count,
            "capacity_observation_count": self.coordinator.stats_store.stats.capacity_observation_count,
            "depletion_voltage_observation_count": self.coordinator.stats_store.stats.depletion_voltage_observation_count,
            "peukert_observation_count": self.coordinator.stats_store.stats.peukert_observation_count,
            "profile_optimization_active": profile["profile_optimization_active"],
            "effective_capacity_ah": profile["effective_capacity_ah"],
            "effective_depletion_voltage": profile["effective_depletion_voltage"],
            "effective_charge_efficiency": profile["effective_charge_efficiency"],
        }


class BatteryAlgorithmSpreadSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Dedicated algorithm divergence/spread sensor."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
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
            "algorithm_stddev": _algorithm_stddev(self.coordinator),
            "algorithm_outlier": _algorithm_outlier(self.coordinator),
            "confidence_score": _confidence_score(self.coordinator),
            "model_outputs": _model_summary(self.coordinator),
            "model_weighting": self.coordinator.model_weighting,
            "ensemble_weights": self.coordinator.ensemble_weights,
            "selected_algorithm": selected.algorithm if selected else None,
            "selected_soc_percent": selected.soc_percent if selected else None,
            "source_evidence_status": self.coordinator.source_evidence_status,
            **_battery_profile_attrs(self._entry),
        }


class BatteryModelAccuracySensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Learned model accuracy summary sensor."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = SENSOR_NAMES["model_accuracy"]
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_model_accuracy"
        self._attr_suggested_object_id = _object_id(entry, "model_accuracy")
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | None:
        summary = _model_accuracy_summary(self.coordinator)
        average_accuracy = summary["average_accuracy"]
        if average_accuracy is None:
            return None
        return round(float(average_accuracy) * 100.0, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        summary = _model_accuracy_summary(self.coordinator)
        return {
            "average_accuracy": summary["average_accuracy"],
            "best_model": summary["best_model"],
            "worst_model": summary["worst_model"],
            "learned_model_count": summary["learned_model_count"],
            "model_accuracy": summary["model_accuracy"],
            "confidence_score": _confidence_score(self.coordinator),
            "algorithm_spread": self.coordinator.algorithm_spread,
            "source_evidence_status": self.coordinator.source_evidence_status,
            **_battery_profile_attrs(self._entry),
        }


class BatteryPredictionHealthSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Operational health sensor for prediction quality."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
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
        confidence_score = _confidence_score(self.coordinator)
        event_state = self.coordinator.event_state
        if confidence_score is not None and confidence_score < 45:
            return "degraded"
        if data.confidence == "low":
            return "degraded"
        if event_state is not None and event_state.state == "unknown":
            return "limited"
        if self.coordinator.algorithm_spread is not None and self.coordinator.algorithm_spread > 20:
            return "divergent"
        if confidence_score is not None and confidence_score < 70:
            return "limited"
        return "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {}
        event_state = self.coordinator.event_state
        stats = self.coordinator.stats_store.stats
        profile = self.coordinator.stats_store.optimized_profile(stats.configured_capacity_ah or 0.0)
        return {
            "algorithm": data.algorithm,
            "confidence": data.confidence,
            "confidence_score": _confidence_score(self.coordinator),
            "mode": data.mode,
            "selected_soc_percent": data.soc_percent,
            "algorithm_spread": self.coordinator.algorithm_spread,
            "algorithm_stddev": _algorithm_stddev(self.coordinator),
            "algorithm_outlier": _algorithm_outlier(self.coordinator),
            "model_outputs": _model_summary(self.coordinator),
            "model_accuracy": stats.model_accuracy,
            "model_weighting": self.coordinator.model_weighting,
            "ensemble_weights": self.coordinator.ensemble_weights,
            **_battery_profile_attrs(self._entry),
            "health_confidence": stats.health_confidence,
            "capacity_confidence": stats.capacity_confidence,
            "peukert_confidence": stats.peukert_confidence,
            "learned_peukert_exponent": stats.learned_peukert_exponent,
            "peukert_observation_count": stats.peukert_observation_count,
            "profile_optimization_active": profile["profile_optimization_active"],
            "effective_capacity_ah": profile["effective_capacity_ah"],
            "effective_charge_efficiency": profile["effective_charge_efficiency"],
            "battery_ageing_rate_percent_per_100_cycles": profile["battery_ageing_rate_percent_per_100_cycles"],
            "event_state": event_state.state if event_state else None,
            "event_evidence": event_state.evidence if event_state else [],
            "calibration_anchor": event_state.calibration_anchor if event_state else False,
            "calibration_allowed": self.coordinator.calibration_allowed,
            "source_evidence_status": self.coordinator.source_evidence_status,
            "history_window_minutes": runtime_config(self.coordinator.config_entry).get(CONF_HISTORY_WINDOW_MINUTES),
            "update_count": stats.update_count,
            "last_seen": stats.last_seen,
            "reason": data.reason,
        }


class BatteryCalibrationStatusSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Calibration evidence readiness sensor."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
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
        profile = self.coordinator.stats_store.optimized_profile(stats.configured_capacity_ah or 0.0)
        return {
            "readiness_percent": self.native_value,
            "confidence_score": _confidence_score(self.coordinator),
            "algorithm_spread": self.coordinator.algorithm_spread,
            "algorithm_stddev": _algorithm_stddev(self.coordinator),
            "algorithm_outlier": _algorithm_outlier(self.coordinator),
            "model_outputs": _model_summary(self.coordinator),
            "model_accuracy": stats.model_accuracy,
            "model_weighting": self.coordinator.model_weighting,
            "ensemble_weights": self.coordinator.ensemble_weights,
            **_battery_profile_attrs(self._entry),
            "health_confidence": stats.health_confidence,
            "capacity_confidence": stats.capacity_confidence,
            "peukert_confidence": stats.peukert_confidence,
            "learned_peukert_exponent": stats.learned_peukert_exponent,
            "profile_optimization_active": profile["profile_optimization_active"],
            "effective_capacity_ah": profile["effective_capacity_ah"],
            "effective_charge_efficiency": profile["effective_charge_efficiency"],
            "battery_ageing_rate_percent_per_100_cycles": profile["battery_ageing_rate_percent_per_100_cycles"],
            "health_observation_count": stats.health_observation_count,
            "capacity_observation_count": stats.capacity_observation_count,
            "peukert_observation_count": stats.peukert_observation_count,
            "update_count": stats.update_count,
            "calibration_anchor_events": stats.calibration_anchor_events,
            "calibration_allowed": self.coordinator.calibration_allowed,
            "source_evidence_status": self.coordinator.source_evidence_status,
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
    data = runtime_config(entry)
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
