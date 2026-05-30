"""Constants for Battery Remaining Time."""

from __future__ import annotations

DOMAIN = "battery_remaining_time"
PLATFORMS = ["sensor"]

CONF_ALGORITHM = "algorithm"
CONF_BATTERY_CAPACITY_AH = "battery_capacity_ah"
CONF_NOMINAL_VOLTAGE = "nominal_voltage"
CONF_VOLTAGE_SENSOR = "voltage_sensor"
CONF_CURRENT_SENSOR = "current_sensor"
CONF_CHARGE_POWER_SENSOR = "charge_power_sensor"
CONF_DISCHARGE_POWER_SENSOR = "discharge_power_sensor"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_HISTORY_WINDOW_MINUTES = "history_window_minutes"

ALGORITHM_VOLTAGE_ONLY = "voltage_only"
ALGORITHM_CURRENT_FLOW = "current_flow"
ALGORITHM_POWER_FLOW = "power_flow"
ALGORITHM_HYBRID_LEAD_ACID = "hybrid_lead_acid"
ALGORITHM_ADAPTIVE_HYBRID = "adaptive_hybrid"

ALGORITHMS = [
    ALGORITHM_VOLTAGE_ONLY,
    ALGORITHM_CURRENT_FLOW,
    ALGORITHM_POWER_FLOW,
    ALGORITHM_HYBRID_LEAD_ACID,
    ALGORITHM_ADAPTIVE_HYBRID,
]

DEFAULT_ALGORITHM = ALGORITHM_HYBRID_LEAD_ACID
DEFAULT_NOMINAL_VOLTAGE = 12.0
DEFAULT_UPDATE_INTERVAL = 60
DEFAULT_HISTORY_WINDOW_MINUTES = 60

ATTR_ALGORITHM = "algorithm"
ATTR_CONFIDENCE = "confidence"
ATTR_REASON = "reason"
ATTR_SOC_PERCENT = "soc_percent"
ATTR_MODE = "mode"
ATTR_HISTORY_WINDOW_MINUTES = "history_window_minutes"

MODE_CHARGING = "charging"
MODE_DISCHARGING = "discharging"
MODE_IDLE = "idle"
MODE_UNKNOWN = "unknown"
