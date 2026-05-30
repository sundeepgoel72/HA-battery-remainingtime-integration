"""Config flow for Battery Remaining Time."""

from __future__ import annotations

from typing import Any

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
    CONF_ALGORITHM,
    CONF_BATTERY_CAPACITY_AH,
    CONF_CHARGE_POWER_SENSOR,
    CONF_CURRENT_SENSOR,
    CONF_DISCHARGE_POWER_SENSOR,
    CONF_HISTORY_WINDOW_MINUTES,
    CONF_NOMINAL_VOLTAGE,
    CONF_TEMPERATURE_SENSOR,
    CONF_UPDATE_INTERVAL,
    CONF_VOLTAGE_SENSOR,
    DEFAULT_ALGORITHM,
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


class BatteryRemainingTimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Battery Remaining Time."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial setup step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_NAME])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return options flow."""
        return BatteryRemainingTimeOptionsFlow(config_entry)


class BatteryRemainingTimeOptionsFlow(config_entries.OptionsFlow):
    """Options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        if user_input is not None:
            merged = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self.config_entry, data=merged)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="init", data_schema=_schema(self.config_entry.data))


def _entity_selector() -> selector.EntitySelector:
    """Return sensor entity selector."""
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build setup/options schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "Lead Acid Battery")): str,
            vol.Required(CONF_ALGORITHM, default=defaults.get(CONF_ALGORITHM, DEFAULT_ALGORITHM)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=ALGORITHM_OPTIONS)
            ),
            vol.Required(CONF_BATTERY_CAPACITY_AH, default=defaults.get(CONF_BATTERY_CAPACITY_AH, 150.0)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=5000, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_NOMINAL_VOLTAGE, default=defaults.get(CONF_NOMINAL_VOLTAGE, DEFAULT_NOMINAL_VOLTAGE)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=["12", "24", "48"])
            ),
            vol.Required(CONF_VOLTAGE_SENSOR, default=defaults.get(CONF_VOLTAGE_SENSOR)): _entity_selector(),
            vol.Optional(CONF_CURRENT_SENSOR, default=defaults.get(CONF_CURRENT_SENSOR)): _entity_selector(),
            vol.Optional(CONF_CHARGE_POWER_SENSOR, default=defaults.get(CONF_CHARGE_POWER_SENSOR)): _entity_selector(),
            vol.Optional(CONF_DISCHARGE_POWER_SENSOR, default=defaults.get(CONF_DISCHARGE_POWER_SENSOR)): _entity_selector(),
            vol.Optional(CONF_TEMPERATURE_SENSOR, default=defaults.get(CONF_TEMPERATURE_SENSOR)): _entity_selector(),
            vol.Required(CONF_HISTORY_WINDOW_MINUTES, default=defaults.get(CONF_HISTORY_WINDOW_MINUTES, DEFAULT_HISTORY_WINDOW_MINUTES)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=10080, step=5, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_UPDATE_INTERVAL, default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=10, max=3600, step=10, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX)
            ),
        }
    )
