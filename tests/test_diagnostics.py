"""Tests for Home Assistant diagnostics support."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from custom_components.battery_remaining_time.const import DOMAIN
from custom_components.battery_remaining_time.diagnostics import async_get_config_entry_diagnostics


def test_config_entry_diagnostics_redact_entity_ids_and_name() -> None:
    """Diagnostics exports should redact configured entity identifiers and names."""
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Battery",
        data={
            "name": "Main Battery",
            "voltage_sensor": "sensor.battery_voltage",
            "current_sensor": "sensor.battery_current",
            "battery_capacity_ah": 150.0,
        },
        options={"temperature_sensor": "sensor.battery_temperature"},
    )
    stats = SimpleNamespace(
        configured_capacity_ah=150.0,
        as_dict=lambda: {"configured_capacity_ah": 150.0, "peukert_confidence": "low"},
    )
    coordinator = SimpleNamespace(
        data=None,
        event_state=None,
        algorithm_spread=None,
        model_telemetry={"ensemble": {"soc_percent": 95.0}},
        model_weighting={"strategy": "adaptive_accuracy_bounded"},
        ensemble_weights={"ensemble": 1.0},
        stats_store=SimpleNamespace(
            stats=stats,
            optimized_profile=lambda configured_capacity: {
                "profile_optimization_active": False,
                "effective_capacity_ah": configured_capacity,
                "effective_charge_efficiency": 0.85,
            },
        ),
        config_entry=entry,
    )
    hass = SimpleNamespace(data={DOMAIN: {entry.entry_id: coordinator}})

    diagnostics = asyncio.run(async_get_config_entry_diagnostics(hass, entry))

    assert diagnostics["entry"]["data"]["name"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["voltage_sensor"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["current_sensor"] == "**REDACTED**"
    assert diagnostics["entry"]["options"]["temperature_sensor"] == "**REDACTED**"
    assert diagnostics["entry"]["runtime_config"]["name"] == "**REDACTED**"
