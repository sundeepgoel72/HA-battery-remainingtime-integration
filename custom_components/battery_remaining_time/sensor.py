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

from .const import ATTR_ALGORITHM, ATTR_CONFIDENCE, ATTR_HISTORY_WINDOW_MINUTES, ATTR_MODE, ATTR_REASON, ATTR_SOC_PERCENT, DOMAIN
from .coordinator import BatteryRemainingTimeCoordinator
from .predictor import BatteryPrediction


@dataclass(frozen=True, kw_only=True)
class BatterySensorDescription(SensorEntityDescription):
    """Battery forecast sensor description."""

    value_fn: Callable[[BatteryPrediction], Any]


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
    BatterySensorDescription(
        key="mode",
        translation_key="mode",
        value_fn=lambda data: data.mode,
    ),
    BatterySensorDescription(
        key="confidence",
        translation_key="confidence",
        value_fn=lambda data: data.confidence,
    ),
    BatterySensorDescription(
        key="algorithm",
        translation_key="algorithm",
        value_fn=lambda data: data.algorithm,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Battery Remaining Time sensors."""
    coordinator: BatteryRemainingTimeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BatteryRemainingTimeSensor(coordinator, entry, description) for description in SENSORS)


class BatteryRemainingTimeSensor(CoordinatorEntity[BatteryRemainingTimeCoordinator], SensorEntity):
    """Battery remaining time sensor."""

    entity_description: BatterySensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: BatteryRemainingTimeCoordinator, entry: ConfigEntry, description: BatterySensorDescription) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Sundeep Goel",
            "model": "Lead Acid Forecast Engine",
        }

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
        history_window = self.coordinator.config_entry.data.get(ATTR_HISTORY_WINDOW_MINUTES)
        return {
            ATTR_ALGORITHM: data.algorithm,
            ATTR_SOC_PERCENT: data.soc_percent,
            ATTR_MODE: data.mode,
            ATTR_CONFIDENCE: data.confidence,
            ATTR_REASON: data.reason,
            ATTR_HISTORY_WINDOW_MINUTES: history_window,
        }
