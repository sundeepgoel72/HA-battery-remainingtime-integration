"""Tests for runtime config and config-flow helpers."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.const import CONF_NAME

from custom_components.battery_remaining_time.config_flow import (
    _default_depletion_voltage,
    _maybe_update_entry_title,
    _stable_unique_id,
)
from custom_components.battery_remaining_time.const import (
    CONF_ALGORITHM,
    CONF_BATTERY_CAPACITY_AH,
    CONF_BATTERY_TYPE,
    CONF_CURRENT_SENSOR,
    CONF_DEPLETION_VOLTAGE,
    CONF_HISTORY_WINDOW_MINUTES,
    CONF_NOMINAL_VOLTAGE,
    CONF_UPDATE_INTERVAL,
    CONF_VOLTAGE_SENSOR,
)
from custom_components.battery_remaining_time.runtime import runtime_config


def _config_payload(name: str) -> dict[str, object]:
    return {
        CONF_NAME: name,
        CONF_ALGORITHM: "ensemble",
        CONF_BATTERY_TYPE: "tubular",
        CONF_BATTERY_CAPACITY_AH: 150.0,
        CONF_NOMINAL_VOLTAGE: "12",
        CONF_VOLTAGE_SENSOR: "sensor.battery_voltage",
        CONF_CURRENT_SENSOR: "sensor.battery_current",
        CONF_HISTORY_WINDOW_MINUTES: 60,
        CONF_UPDATE_INTERVAL: 60,
    }


def test_stable_unique_id_ignores_display_name() -> None:
    """Renaming the entry should not change the battery identity."""
    first = _stable_unique_id(_config_payload("Main Battery"))
    second = _stable_unique_id(_config_payload("Renamed Battery"))

    assert first == second


def test_runtime_config_options_override_data() -> None:
    """Runtime config should prefer mutable options over setup data."""
    entry = SimpleNamespace(
        data={CONF_UPDATE_INTERVAL: 60, CONF_HISTORY_WINDOW_MINUTES: 120},
        options={CONF_UPDATE_INTERVAL: 30},
    )

    data = runtime_config(entry)

    assert data[CONF_UPDATE_INTERVAL] == 30
    assert data[CONF_HISTORY_WINDOW_MINUTES] == 120


def test_default_depletion_voltage_prefers_configured_value() -> None:
    """Configured depletion voltage should override nominal-derived defaults."""
    defaults = {
        CONF_DEPLETION_VOLTAGE: 11.8,
        CONF_NOMINAL_VOLTAGE: 12.0,
    }

    assert _default_depletion_voltage(defaults) == 11.8


def test_options_title_sync_updates_config_entry_title() -> None:
    """Changing the editable battery name should update the entry title."""

    class FakeConfigEntries:
        def __init__(self) -> None:
            self.calls: list[tuple[object, str]] = []

        def async_update_entry(self, entry: object, *, title: str) -> None:
            self.calls.append((entry, title))

    manager = FakeConfigEntries()
    hass = SimpleNamespace(config_entries=manager)
    entry = SimpleNamespace(title="Old Battery")

    _maybe_update_entry_title(hass, entry, {CONF_NAME: "New Battery"})

    assert manager.calls == [(entry, "New Battery")]
