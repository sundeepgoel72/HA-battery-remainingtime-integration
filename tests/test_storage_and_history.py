"""Tests for storage learning and recorder helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from custom_components.battery_remaining_time.events import BatteryEventState
from custom_components.battery_remaining_time.history import history_start_time
from custom_components.battery_remaining_time.predictor import (
    BatteryInputs,
    BatteryPrediction,
    HistoryPoint,
)
from custom_components.battery_remaining_time.storage import (
    BatteryStats,
    BatteryStatsStore,
    DEFAULT_PEUCKERT_EXPONENT,
    _new_history_points,
)


def test_new_history_points_filters_processed_timestamps() -> None:
    """Storage learning should only consume history points newer than the checkpoint."""
    older = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    checkpoint = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    history = [
        HistoryPoint(1.0, timestamp=older),
        HistoryPoint(1.0, timestamp=checkpoint),
        HistoryPoint(1.0, timestamp=newer),
    ]

    points = _new_history_points(history, checkpoint.isoformat())

    assert points == [history[2]]


def test_history_start_time_uses_newer_checkpoint() -> None:
    """Recorder queries should start at the checkpoint when it is newer than the window."""
    checkpoint = datetime.now(timezone.utc) - timedelta(minutes=5)

    start = history_start_time(60, checkpoint)

    assert start == checkpoint


def test_model_accuracy_uses_raw_anchor_evidence_not_selected_prediction() -> None:
    """Accuracy learning should reward models close to the raw calibration anchor."""
    store = object.__new__(BatteryStatsStore)
    store.stats = BatteryStats()
    inputs = BatteryInputs(
        algorithm="ensemble",
        capacity_ah=100.0,
        nominal_voltage=12.0,
        voltage=14.4,
        depletion_voltage=11.6,
    )
    event_state = BatteryEventState("float", ["high_charge_voltage"], calibration_anchor=True)
    model_predictions = {
        "accurate": BatteryPrediction("accurate", 100.0, "charging", 120.0, None, 0.0, "high", "test"),
        "biased": BatteryPrediction("biased", 50.0, "charging", 120.0, None, 2.0, "high", "test"),
    }

    store._record_model_performance("2026-01-01T00:00:00+00:00", inputs, event_state, model_predictions)

    assert store.stats.model_error_stats["accurate"]["last_error"] == 0.0
    assert store.stats.model_error_stats["biased"]["last_error"] == 50.0
    assert store.stats.model_accuracy["accurate"] > store.stats.model_accuracy["biased"]


def test_peukert_learning_stores_observation_but_falls_back_when_confidence_low() -> None:
    """A single real discharge cycle should not override the configured/default exponent."""
    store = object.__new__(BatteryStatsStore)
    store.stats = BatteryStats()
    inputs = BatteryInputs(
        algorithm="peukert",
        capacity_ah=100.0,
        nominal_voltage=12.0,
        depletion_voltage=11.8,
    )
    event_state = BatteryEventState("low_battery", ["depletion_voltage"], calibration_anchor=True)
    prediction = BatteryPrediction("peukert", 0.0, "discharging", -120.0, 4.0, None, "medium", "test")

    store._record_peukert_observation("2026-01-01T00:00:00+00:00", inputs, prediction, event_state, _peukert_history())

    assert store.stats.peukert_observation_count == 1
    assert store.stats.learned_peukert_exponent is not None
    assert store.stats.peukert_confidence == "low"
    assert store.effective_peukert_exponent() == DEFAULT_PEUCKERT_EXPONENT


def test_peukert_learning_uses_learned_exponent_after_medium_confidence() -> None:
    """Repeated low-battery discharge observations should become trusted gradually."""
    store = object.__new__(BatteryStatsStore)
    store.stats = BatteryStats()
    inputs = BatteryInputs(
        algorithm="peukert",
        capacity_ah=100.0,
        nominal_voltage=12.0,
        depletion_voltage=11.8,
    )
    event_state = BatteryEventState("low_battery", ["depletion_voltage"], calibration_anchor=True)
    prediction = BatteryPrediction("peukert", 0.0, "discharging", -120.0, 4.0, None, "medium", "test")

    for index in range(3):
        store._record_peukert_observation(f"2026-01-01T0{index}:00:00+00:00", inputs, prediction, event_state, _peukert_history())

    assert store.stats.peukert_observation_count == 3
    assert store.stats.peukert_confidence == "medium"
    assert store.stats.learned_peukert_exponent is not None
    assert store.stats.learned_peukert_exponent > DEFAULT_PEUCKERT_EXPONENT
    assert store.effective_peukert_exponent() == store.stats.learned_peukert_exponent


def test_profile_optimization_uses_trusted_learned_capacity_and_efficiency() -> None:
    """Phase 4 optimization should only apply learned values once confidence is trusted."""
    store = object.__new__(BatteryStatsStore)
    store.stats = BatteryStats(
        learned_capacity_ah=82.0,
        capacity_confidence="medium",
        learned_charge_efficiency=0.91,
        charge_efficiency_confidence="high",
        capacity_retention_percent=82.0,
        estimated_cycle_equivalents=120.0,
    )

    profile = store.optimized_profile(100.0)

    assert store.effective_capacity_ah(100.0) == 82.0
    assert store.effective_charge_efficiency() == 0.91
    assert profile["profile_optimization_active"] is True
    assert profile["capacity_source"] == "learned"
    assert profile["charge_efficiency_source"] == "learned"
    assert profile["battery_ageing_rate_percent_per_100_cycles"] == 15.0


def test_profile_optimization_falls_back_when_learning_confidence_is_low() -> None:
    """Low-confidence learners should not alter the runtime battery profile."""
    store = object.__new__(BatteryStatsStore)
    store.stats = BatteryStats(
        learned_capacity_ah=75.0,
        capacity_confidence="low",
        learned_charge_efficiency=0.95,
        charge_efficiency_confidence="low",
    )

    profile = store.optimized_profile(100.0)

    assert store.effective_capacity_ah(100.0) == 100.0
    assert store.effective_charge_efficiency() == 0.85
    assert profile["profile_optimization_active"] is False
    assert profile["capacity_source"] == "configured"
    assert profile["charge_efficiency_source"] == "configured"


def _peukert_history() -> list[HistoryPoint]:
    """Return a sustained recorder discharge window ending at low battery."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        HistoryPoint(1.0, voltage=12.4, current=-10.0, timestamp=start),
        HistoryPoint(1.0, voltage=12.25, current=-10.0, timestamp=start + timedelta(hours=1)),
        HistoryPoint(1.0, voltage=12.05, current=-10.0, timestamp=start + timedelta(hours=2)),
        HistoryPoint(1.0, voltage=11.8, current=-10.0, timestamp=start + timedelta(hours=3)),
    ]
