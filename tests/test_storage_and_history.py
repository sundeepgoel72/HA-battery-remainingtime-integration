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
