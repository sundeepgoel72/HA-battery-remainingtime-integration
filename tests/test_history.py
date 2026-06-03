"""Tests for recorder history helpers."""

from __future__ import annotations

import importlib
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import custom_components.battery_remaining_time.history as history_module
from custom_components.battery_remaining_time.history import (
    _normalize_raw_history,
    async_get_history_points,
    build_history_points,
    history_start_time,
)


def test_history_start_time_uses_newer_checkpoint() -> None:
    """Recorder queries should start at the checkpoint when it is newer than the window."""
    checkpoint = datetime.now(timezone.utc) - timedelta(minutes=5)

    start = history_start_time(60, checkpoint)

    assert start == checkpoint


def test_normalize_raw_history_supports_list_shape() -> None:
    """Recorder list output should be normalized into entity_id buckets."""
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    voltage = SimpleNamespace(
        entity_id="sensor.voltage",
        state="12.4",
        last_updated=stamp,
        last_changed=stamp,
    )
    current = SimpleNamespace(
        entity_id="sensor.current",
        state="-4.2",
        last_updated=stamp,
        last_changed=stamp,
    )

    normalized = _normalize_raw_history([[voltage], [current]], ["sensor.voltage", "sensor.current"])

    assert normalized["sensor.voltage"] == [voltage]
    assert normalized["sensor.current"] == [current]


def test_build_history_points_normalizes_recorder_state_rows() -> None:
    """Recorder states should be converted into aligned history points."""
    first = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    second = first + timedelta(minutes=5)
    third = second + timedelta(minutes=5)
    raw = {
        "sensor.voltage": [
            SimpleNamespace(entity_id="sensor.voltage", state="12.4", last_updated=first, last_changed=first),
            SimpleNamespace(entity_id="sensor.voltage", state="12.3", last_updated=second, last_changed=second),
            SimpleNamespace(entity_id="sensor.voltage", state="12.2", last_updated=third, last_changed=third),
        ],
        "sensor.current": [
            SimpleNamespace(entity_id="sensor.current", state="-5.0", last_updated=first, last_changed=first),
            SimpleNamespace(entity_id="sensor.current", state="-4.5", last_updated=third, last_changed=third),
        ],
    }

    points = build_history_points(
        raw,
        {
            "voltage": "sensor.voltage",
            "current": "sensor.current",
            "charge_power": None,
            "discharge_power": None,
            "temperature": None,
        },
    )

    assert len(points) == 2
    assert points[0].voltage == 12.3
    assert points[0].current == -5.0
    assert round(points[0].dt_hours, 6) == round(5 / 60, 6)
    assert points[1].voltage == 12.2
    assert points[1].current == -4.5


def test_history_module_does_not_import_recorder_at_module_load() -> None:
    """History helpers should keep Recorder imports lazy."""
    sys.modules.pop("homeassistant.components.recorder", None)
    sys.modules.pop("homeassistant.components.recorder.history", None)

    importlib.reload(history_module)

    assert "homeassistant.components.recorder" not in sys.modules
    assert "homeassistant.components.recorder.history" not in sys.modules


def test_async_get_history_points_returns_empty_when_recorder_fails() -> None:
    """Recorder failures should degrade to an empty history set."""

    async def scenario() -> None:
        hass = SimpleNamespace()
        recorder_instance = SimpleNamespace(async_add_executor_job=AsyncMock(side_effect=RuntimeError("db down")))
        with patch(
            "homeassistant.components.recorder.get_instance",
            return_value=recorder_instance,
        ):
            points = await async_get_history_points(
                hass,
                {"voltage": "sensor.voltage", "current": "sensor.current"},
                60,
            )
        assert points == []

    asyncio.run(scenario())
