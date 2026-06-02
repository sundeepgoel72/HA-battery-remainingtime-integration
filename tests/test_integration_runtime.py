"""Tests for integration runtime behavior and entry lifecycle."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.battery_remaining_time import _async_update_listener, async_setup_entry, async_unload_entry
from custom_components.battery_remaining_time.const import (
    CONF_ALGORITHM,
    CONF_BATTERY_CAPACITY_AH,
    CONF_CURRENT_SENSOR,
    CONF_HISTORY_WINDOW_MINUTES,
    CONF_NOMINAL_VOLTAGE,
    CONF_UPDATE_INTERVAL,
    CONF_VOLTAGE_SENSOR,
    DOMAIN,
)
from custom_components.battery_remaining_time.coordinator import BatteryRemainingTimeCoordinator
from custom_components.battery_remaining_time.events import BatteryEventState
from custom_components.battery_remaining_time.predictor import BatteryPrediction, HistoryPoint
from custom_components.battery_remaining_time.storage import BatteryStats


class FakeEntry:
    """Minimal config entry surface for integration tests."""

    def __init__(self) -> None:
        self.entry_id = "entry-1"
        self.title = "Main Battery"
        self.data = {
            CONF_ALGORITHM: "ensemble",
            CONF_BATTERY_CAPACITY_AH: 150.0,
            CONF_NOMINAL_VOLTAGE: 12.0,
            CONF_VOLTAGE_SENSOR: "sensor.battery_voltage",
            CONF_CURRENT_SENSOR: "sensor.battery_current",
            CONF_HISTORY_WINDOW_MINUTES: 60,
            CONF_UPDATE_INTERVAL: 60,
        }
        self.options: dict[str, object] = {}
        self._unload_callbacks: list[object] = []

    def add_update_listener(self, listener):
        return listener

    def async_on_unload(self, callback):
        self._unload_callbacks.append(callback)


def _entry() -> FakeEntry:
    return FakeEntry()


def _fake_hass() -> SimpleNamespace:
    return SimpleNamespace(
        data={},
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(return_value=True),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(return_value=True),
        ),
        states=SimpleNamespace(get=lambda entity_id: None),
    )


def _coordinator(entry: FakeEntry) -> BatteryRemainingTimeCoordinator:
    coordinator = object.__new__(BatteryRemainingTimeCoordinator)
    coordinator.config_entry = entry
    coordinator.hass = _fake_hass()
    coordinator._stats_loaded = False
    coordinator._last_soc = None
    coordinator._last_history_fetch_timestamp = None
    coordinator.event_state = None
    coordinator.model_predictions = {}
    coordinator.model_telemetry = {}
    coordinator.algorithm_spread = None
    coordinator.ensemble_weights = {}
    coordinator.model_weighting = {}
    coordinator.source_evidence_status = "unknown"
    coordinator.calibration_allowed = False
    coordinator.stats_store = SimpleNamespace(
        stats=BatteryStats(),
        async_load=AsyncMock(return_value=None),
        async_record_update=AsyncMock(return_value=None),
        optimized_profile=lambda configured_capacity: {
            "effective_capacity_ah": configured_capacity,
            "effective_charge_efficiency": 0.85,
        },
        effective_peukert_exponent=lambda: 1.2,
    )
    return coordinator


def test_async_setup_and_unload_entry_manage_hass_data() -> None:
    """Entry setup and unload should manage coordinator lifetime cleanly."""

    async def scenario() -> None:
        hass = _fake_hass()
        entry = _entry()
        fake_coordinator = SimpleNamespace(async_config_entry_first_refresh=AsyncMock(return_value=None))
        with patch("custom_components.battery_remaining_time.BatteryRemainingTimeCoordinator", return_value=fake_coordinator):
            assert await async_setup_entry(hass, entry) is True
            assert hass.data[DOMAIN][entry.entry_id] is fake_coordinator

            assert await async_unload_entry(hass, entry) is True
            assert entry.entry_id not in hass.data[DOMAIN]

    asyncio.run(scenario())


def test_update_listener_requests_reload() -> None:
    """Options/data updates should trigger a config entry reload."""

    async def scenario() -> None:
        hass = _fake_hass()
        entry = _entry()
        await _async_update_listener(hass, entry)
        hass.config_entries.async_reload.assert_awaited_once_with(entry.entry_id)

    asyncio.run(scenario())


def test_runtime_update_creates_issue_when_sources_and_history_are_unavailable() -> None:
    """Coordinator should refuse to forecast when neither live nor recorder data exists."""

    async def scenario() -> None:
        entry = _entry()
        coordinator = _coordinator(entry)
        with (
            patch(
                "custom_components.battery_remaining_time.coordinator.async_get_history_points",
                AsyncMock(return_value=[]),
            ),
            patch("custom_components.battery_remaining_time.coordinator.ir.async_create_issue") as create_issue,
        ):
            try:
                await coordinator._async_update_data()
            except UpdateFailed:
                pass
            else:
                raise AssertionError("Expected UpdateFailed when all source evidence is missing")

        create_issue.assert_called_once()

    asyncio.run(scenario())


def test_runtime_update_uses_recorder_fallback_when_live_sensors_are_missing() -> None:
    """Recorder history should provide fallback values during transient startup gaps."""

    async def scenario() -> None:
        entry = _entry()
        coordinator = _coordinator(entry)
        prediction = BatteryPrediction("ensemble", 95.7, "idle", 0.0, None, None, "high", "fallback")
        history = [
            HistoryPoint(
                dt_hours=5 / 60,
                voltage=25.51,
                current=0.07,
            )
        ]
        with (
            patch(
                "custom_components.battery_remaining_time.coordinator.async_get_history_points",
                AsyncMock(return_value=history),
            ),
            patch(
                "custom_components.battery_remaining_time.coordinator.all_model_predictions",
                return_value={"ensemble": prediction},
            ),
            patch(
                "custom_components.battery_remaining_time.coordinator.ensemble_model_weights",
                return_value={"ensemble": 1.0},
            ),
            patch(
                "custom_components.battery_remaining_time.coordinator.ensemble_model_weighting_strategy",
                return_value={"strategy": "single"},
            ),
            patch(
                "custom_components.battery_remaining_time.coordinator.detect_event_state",
                return_value=BatteryEventState("resting", ["voltage_stable"], calibration_anchor=False),
            ),
            patch("custom_components.battery_remaining_time.coordinator.ir.async_delete_issue") as delete_issue,
        ):
            result = await coordinator._async_update_data()

        assert result.soc_percent == 95.7
        assert coordinator.model_predictions["ensemble"] == prediction
        delete_issue.assert_called_once()

    asyncio.run(scenario())


def test_runtime_update_rate_limits_impossible_soc_drop_and_blocks_calibration() -> None:
    """High-spread collapses should be clamped and kept out of calibration learning."""

    async def scenario() -> None:
        entry = _entry()
        coordinator = _coordinator(entry)
        coordinator._last_soc = 97.0
        prediction = BatteryPrediction("ensemble", 0.0, "idle", 0.0, None, None, "high", "rogue collapse")
        history = [HistoryPoint(dt_hours=5 / 60, voltage=12.8, current=0.0)]
        with (
            patch(
                "custom_components.battery_remaining_time.coordinator.async_get_history_points",
                AsyncMock(return_value=history),
            ),
            patch(
                "custom_components.battery_remaining_time.coordinator.all_model_predictions",
                return_value={
                    "ensemble": prediction,
                    "voltage_only": BatteryPrediction("voltage_only", 97.0, "idle", 0.0, None, None, "high", "ocv"),
                    "current_flow": BatteryPrediction("current_flow", 0.0, "idle", 0.0, None, None, "low", "rogue"),
                },
            ),
            patch(
                "custom_components.battery_remaining_time.coordinator.ensemble_model_weights",
                return_value={"ensemble": 1.0},
            ),
            patch(
                "custom_components.battery_remaining_time.coordinator.ensemble_model_weighting_strategy",
                return_value={"strategy": "single"},
            ),
            patch(
                "custom_components.battery_remaining_time.coordinator.algorithm_spread",
                return_value=97.0,
            ),
            patch(
                "custom_components.battery_remaining_time.coordinator.detect_event_state",
                return_value=BatteryEventState("low_battery", ["soc_below_15"], calibration_anchor=True),
            ),
            patch("custom_components.battery_remaining_time.coordinator.ir.async_delete_issue"),
        ):
            result = await coordinator._async_update_data()

        assert result.soc_percent == 96.0
        assert result.confidence == "very_low"
        assert coordinator.event_state.calibration_anchor is False
        assert coordinator.calibration_allowed is False

    asyncio.run(scenario())
