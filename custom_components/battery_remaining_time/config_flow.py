"""Config flow for Battery Remaining Time."""

from __future__ import annotations

from json import dumps
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    ALGORITHM_ADAPTIVE_HYBRID,
    ALGORITHM_CURRENT_FLOW,
    ALGORITHM_HYBRID_LEAD_ACID,
    ALGORITHM_POWER_FLOW,
    ALGORITHM_VOLTAGE_ONLY,
    BATTERY_TYPE_LABELS,
    BATTERY_TYPES,
    CONF_ALGORITHM,
    CONF_BATTERY_BRAND_MODEL,
    CONF_BATTERY_CAPACITY_AH,
    CONF_BATTERY_TYPE,
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
    DEFAULT_BATTERY_BRAND_MODEL,
    DEFAULT_BATTERY_TYPE,
    DEFAULT_DEPLETION_VOLTAGE_FACTOR,
    DEFAULT_HISTORY_WINDOW_MINUTES,
    DEFAULT_NOMINAL_VOLTAGE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

ALGORITHM_OPTIONS = [
    ALGORITHM_VOLTAGE_ONLY,
    ALGORITHM_CURRENT_FLOW,
    ALGORITHM_POWER_FLOW,
    "peukert",
    ALGORITHM_HYBRID_LEAD_ACID,
    "temperature_compensated",
    "kibam",
    "shepherd",
    ALGORITHM_ADAPTIVE_HYBRID,
    "ensemble",
]

BATTERY_TYPE_OPTIONS = [
    {"value": battery_type, "label": BATTERY_TYPE_LABELS[battery_type]}
    for battery_type in BATTERY_TYPES
]


def _default_depletion_voltage(defaults: dict[str, Any]) -> float:
    """Return configured or nominal-derived depletion voltage."""
    if defaults.get(CONF_DEPLETION_VOLTAGE) not in (None, ""):
        return float(defaults[CONF_DEPLETION_VOLTAGE])
    nominal = float(defaults.get(CONF_NOMINAL_VOLTAGE, DEFAULT_NOMINAL_VOLTAGE))
    return round(nominal * DEFAULT_DEPLETION_VOLTAGE_FACTOR, 2)


class BatteryRemainingTimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Battery Remaining Time."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial setup step."""
        if user_input is not None:
            await self.async_set_unique_id(_stable_unique_id(user_input))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema(include_advanced=False))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return options flow."""
        return BatteryRemainingTimeOptionsFlow(config_entry)


class BatteryRemainingTimeOptionsFlow(config_entries.OptionsFlow):
    """Options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        # Home Assistant 2026 exposes config_entry as a read-only property on
        # OptionsFlow. Keep our own reference instead of assigning to it.
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        if user_input is not None:
            merged = {**self._config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self._config_entry, data=merged)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="init", data_schema=_schema(self._config_entry.data, include_advanced=True))


def _entity_selector() -> selector.EntitySelector:
    """Return sensor entity selector."""
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _schema(defaults: dict[str, Any] | None = None, *, include_advanced: bool = False) -> vol.Schema:
    """Build setup/options schema.

    Initial setup asks only for the core battery inputs. Power sensors and
    temperature are optional advanced/fallback settings available from Options.
    """
    defaults = defaults or {}
    fields: dict[Any, Any] = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "Lead Acid Battery")): str,
        vol.Required(CONF_ALGORITHM, default=defaults.get(CONF_ALGORITHM, DEFAULT_ALGORITHM)): selector.SelectSelector(
            selector.SelectSelectorConfig(options=ALGORITHM_OPTIONS)
        ),
        vol.Required(CONF_BATTERY_TYPE, default=defaults.get(CONF_BATTERY_TYPE, DEFAULT_BATTERY_TYPE)): selector.SelectSelector(
            selector.SelectSelectorConfig(options=BATTERY_TYPE_OPTIONS, mode=selector.SelectSelectorMode.DROPDOWN)
        ),
        vol.Optional(CONF_BATTERY_BRAND_MODEL, default=defaults.get(CONF_BATTERY_BRAND_MODEL, DEFAULT_BATTERY_BRAND_MODEL)): str,
        vol.Required(CONF_BATTERY_CAPACITY_AH, default=defaults.get(CONF_BATTERY_CAPACITY_AH, 150.0)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=5000, step=1, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_NOMINAL_VOLTAGE, default=defaults.get(CONF_NOMINAL_VOLTAGE, DEFAULT_NOMINAL_VOLTAGE)): selector.SelectSelector(
            selector.SelectSelectorConfig(options=["12", "24", "36", "48", "60", "72"])
        ),
        vol.Optional(CONF_DEPLETION_VOLTAGE, default=_default_depletion_voltage(defaults)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=1, max=100, step=0.1, unit_of_measurement="V", mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_VOLTAGE_SENSOR, default=defaults.get(CONF_VOLTAGE_SENSOR)): _entity_selector(),
        vol.Optional(CONF_CURRENT_SENSOR, default=defaults.get(CONF_CURRENT_SENSOR)): _entity_selector(),
        vol.Required(CONF_HISTORY_WINDOW_MINUTES, default=defaults.get(CONF_HISTORY_WINDOW_MINUTES, DEFAULT_HISTORY_WINDOW_MINUTES)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=5, max=10080, step=5, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_UPDATE_INTERVAL, default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)): selector.NumberSelector(
            selector.NumberSelectorConfig(min=10, max=3600, step=10, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX)
        ),
    }

    if include_advanced:
        fields.update(
            {
                vol.Optional(CONF_CHARGE_POWER_SENSOR, default=defaults.get(CONF_CHARGE_POWER_SENSOR)): _entity_selector(),
                vol.Optional(CONF_DISCHARGE_POWER_SENSOR, default=defaults.get(CONF_DISCHARGE_POWER_SENSOR)): _entity_selector(),
                vol.Optional(CONF_TEMPERATURE_SENSOR, default=defaults.get(CONF_TEMPERATURE_SENSOR)): _entity_selector(),
            }
        )

    return vol.Schema(fields)


def _stable_unique_id(user_input: dict[str, Any]) -> str:
    """Return a stable unique ID derived from the configured battery inputs."""
    identity = {
        CONF_VOLTAGE_SENSOR: user_input.get(CONF_VOLTAGE_SENSOR),
        CONF_CURRENT_SENSOR: user_input.get(CONF_CURRENT_SENSOR),
        CONF_CHARGE_POWER_SENSOR: user_input.get(CONF_CHARGE_POWER_SENSOR),
        CONF_DISCHARGE_POWER_SENSOR: user_input.get(CONF_DISCHARGE_POWER_SENSOR),
        CONF_TEMPERATURE_SENSOR: user_input.get(CONF_TEMPERATURE_SENSOR),
        CONF_BATTERY_TYPE: user_input.get(CONF_BATTERY_TYPE),
        CONF_BATTERY_CAPACITY_AH: user_input.get(CONF_BATTERY_CAPACITY_AH),
        CONF_NOMINAL_VOLTAGE: user_input.get(CONF_NOMINAL_VOLTAGE),
        CONF_BATTERY_BRAND_MODEL: user_input.get(CONF_BATTERY_BRAND_MODEL, ""),
    }
    payload = dumps(identity, sort_keys=True, separators=(",", ":"))
    return str(uuid5(NAMESPACE_URL, f"{DOMAIN}:{payload}"))
