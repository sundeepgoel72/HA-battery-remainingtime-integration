"""Tests for prediction behavior and sensor helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.battery_remaining_time.const import CONF_BATTERY_TYPE
from custom_components.battery_remaining_time.predictor import (
    BatteryInputs,
    BatteryPrediction,
    confidence_from_spread,
    ensemble_from_predictions,
    ensemble_model_weighting_strategy,
    ensemble_model_weights,
    practical_usable_soc,
    time_to_depletion,
)
from custom_components.battery_remaining_time.sensor import (
    COMPARISON_SENSORS,
    DIAGNOSTIC_ALIAS_SENSORS,
    DEFAULT_EXPECTED_CYCLE_LIFE,
    EXPECTED_CYCLE_LIFE_BY_TYPE,
    HEALTH_SENSORS,
    SENSOR_NAMES,
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


def test_adaptive_ensemble_weights_favor_more_accurate_models_without_dropping_any() -> None:
    """Model accuracy should adjust ensemble weights while keeping every model active."""
    inputs = BatteryInputs(
        algorithm="ensemble",
        capacity_ah=100.0,
        nominal_voltage=12.0,
        voltage=12.4,
        current=-5.0,
        model_accuracy={"accurate": 1.0, "weak": 0.05},
    )
    predictions = {
        "accurate": BatteryPrediction("accurate", 70.0, "discharging", -60.0, 10.0, None, "high", "test"),
        "weak": BatteryPrediction("weak", 20.0, "discharging", -60.0, 10.0, None, "high", "test"),
        "fallback": BatteryPrediction("fallback", 60.0, "discharging", -60.0, 10.0, None, "medium", "test"),
    }

    weights = ensemble_model_weights(inputs, predictions)

    assert set(weights) == set(predictions)
    assert weights["accurate"] > weights["weak"]
    assert all(0.0 < weight <= 0.35 for weight in weights.values())
    assert sum(weights.values()) == pytest.approx(1.0, abs=0.001)


def test_adaptive_ensemble_weighting_strategy_reports_diagnostics() -> None:
    """Weighting metadata should expose the adaptive bounded strategy."""
    inputs = BatteryInputs(
        algorithm="ensemble",
        capacity_ah=100.0,
        nominal_voltage=12.0,
        voltage=12.4,
        current=0.0,
        model_accuracy={"accurate": 1.0},
    )
    predictions = {
        "accurate": BatteryPrediction("accurate", 80.0, "idle", 0.0, None, None, "high", "test"),
        "fallback": BatteryPrediction("fallback", 78.0, "idle", 0.0, None, None, "medium", "test"),
    }

    strategy = ensemble_model_weighting_strategy(inputs, predictions)

    assert strategy["strategy"] == "adaptive_accuracy_bounded"
    assert strategy["active_model_count"] == 2
    assert strategy["accuracy_model_count"] == 1
    assert strategy["resting_context"] is True


@pytest.mark.parametrize(
    ("spread", "count", "expected"),
    [
        (4.9, 5, "high"),
        (10.0, 5, "medium"),
        (20.0, 5, "low"),
        (35.0, 5, "very_low"),
        (None, 1, "low"),
    ],
)
def test_spread_based_confidence_thresholds(spread: float | None, count: int, expected: str) -> None:
    """Ensemble confidence should be driven by model agreement."""
    assert confidence_from_spread(spread, count) == expected


def test_robust_ensemble_uses_resting_anchor_to_reject_rogue_outputs() -> None:
    """A couple of rogue low-output models should not collapse a resting full battery."""
    inputs = BatteryInputs(
        algorithm="ensemble",
        capacity_ah=150.0,
        nominal_voltage=24.0,
        voltage=25.6,
        current=0.0,
    )
    predictions = {
        "voltage_only": BatteryPrediction("voltage_only", 100.0, "idle", 0.0, None, None, "high", "ocv"),
        "shepherd": BatteryPrediction("shepherd", 98.0, "idle", 0.0, None, None, "medium", "shepherd"),
        "hybrid_lead_acid": BatteryPrediction("hybrid_lead_acid", 97.0, "idle", 0.0, None, None, "high", "hybrid"),
        "current_flow": BatteryPrediction("current_flow", 0.0, "idle", 0.0, None, None, "low", "rogue"),
        "peukert": BatteryPrediction("peukert", 0.0, "idle", 0.0, None, None, "medium", "rogue"),
    }

    result = ensemble_from_predictions(inputs, predictions)

    assert result.soc_percent == 98.0
    assert result.confidence == "very_low"


def test_comparison_and_alias_sensor_keys_are_exposed() -> None:
    """Issue #18 observability keys should be present on the sensor surface."""
    comparison_keys = {description.key for description in COMPARISON_SENSORS}
    alias_keys = {description.key for description in DIAGNOSTIC_ALIAS_SENSORS}

    assert {"soc_ocv", "soc_coulomb", "soc_peukert", "soc_hybrid", "soc_ensemble"} <= comparison_keys
    assert {"tte_ocv", "tte_coulomb", "tte_peukert", "tte_hybrid", "tte_ensemble"} <= comparison_keys
    assert {"ttf_ocv", "ttf_coulomb", "ttf_peukert", "ttf_hybrid", "ttf_ensemble"} <= comparison_keys
    assert {"prediction_confidence", "active_algorithm"} <= alias_keys
    assert "model_accuracy" in SENSOR_NAMES
    assert {"usable_soc", "time_to_depletion", "configured_depletion_voltage", "learned_depletion_voltage", "depletion_voltage_confidence"} <= set(SENSOR_NAMES)


def test_depletion_voltage_sensor_surface_is_stable_for_release_smoke() -> None:
    """Release smoke should keep the depletion-voltage sensor names stable."""
    expected = {
        "usable_soc",
        "time_to_depletion",
        "configured_depletion_voltage",
        "learned_depletion_voltage",
        "depletion_voltage_confidence",
    }

    assert expected <= set(SENSOR_NAMES)
