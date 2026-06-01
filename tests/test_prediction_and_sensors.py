"""Tests for prediction behavior and sensor helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.battery_remaining_time.const import CONF_BATTERY_TYPE
from custom_components.battery_remaining_time.predictor import (
    BatteryInputs,
    practical_usable_soc,
    time_to_depletion,
)
from custom_components.battery_remaining_time.sensor import (
    DEFAULT_EXPECTED_CYCLE_LIFE,
    EXPECTED_CYCLE_LIFE_BY_TYPE,
    HEALTH_SENSORS,
    _expected_cycle_life,
)


def test_depletion_voltage_limits_usable_soc_and_depletion_time() -> None:
    """Configured depletion voltage should affect usable SOC and runtime."""
    inputs = BatteryInputs(
        algorithm="ensemble",
        capacity_ah=100.0,
        nominal_voltage=12.0,
        voltage=11.6,
        depletion_voltage=11.6,
    )

    usable_soc = practical_usable_soc(inputs, 50.0)
    runtime = time_to_depletion(inputs, usable_soc, -120.0)

    assert usable_soc == 0.0
    assert runtime == 0.0


@pytest.mark.parametrize(
    ("battery_type", "expected"),
    sorted(EXPECTED_CYCLE_LIFE_BY_TYPE.items()),
)
def test_expected_cycle_life_for_each_supported_type(battery_type: str, expected: float) -> None:
    """Every configured battery type should use its chemistry-specific cycle life."""
    entry = SimpleNamespace(data={CONF_BATTERY_TYPE: battery_type}, options={})

    assert _expected_cycle_life(entry) == expected


def test_expected_cycle_life_defaults_for_unknown_type() -> None:
    """Unknown battery types should fall back to the documented default."""
    entry = SimpleNamespace(data={CONF_BATTERY_TYPE: "unknown"}, options={})

    assert _expected_cycle_life(entry) == DEFAULT_EXPECTED_CYCLE_LIFE


def test_peukert_learning_stats_are_exposed_as_diagnostic_sensors() -> None:
    """Learned Peukert statistics should have stable diagnostic sensor keys."""
    keys = {description.key for description in HEALTH_SENSORS}

    assert "learned_peukert_exponent" in keys
    assert "peukert_confidence" in keys
    assert "peukert_observation_count" in keys
