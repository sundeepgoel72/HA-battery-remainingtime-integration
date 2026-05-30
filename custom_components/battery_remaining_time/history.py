"""Recorder history helpers for Battery Remaining Time."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .predictor import HistoryPoint


def _float_state(state: Any | None) -> float | None:
    if state is None or state.state in {"unknown", "unavailable"}:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _time(state: Any):
    return getattr(state, "last_updated", None) or getattr(state, "last_changed", None)


def _latest(states: list[Any], when) -> float | None:
    selected = None
    for state in states:
        stamp = _time(state)
        if stamp is not None and stamp <= when:
            selected = state
        elif stamp is not None:
            break
    return _float_state(selected or (states[0] if states else None))


def build_history_points(raw: dict[str, list[Any]], entities: dict[str, str | None]) -> list[HistoryPoint]:
    voltage = raw.get(entities.get("voltage") or "", [])
    current = raw.get(entities.get("current") or "", [])
    charge = raw.get(entities.get("charge_power") or "", [])
    discharge = raw.get(entities.get("discharge_power") or "", [])
    temp = raw.get(entities.get("temperature") or "", [])

    stamps = sorted({_time(s) for states in raw.values() for s in states if _time(s) is not None})
    if len(stamps) < 2:
        return []

    points: list[HistoryPoint] = []
    prev = stamps[0]
    for stamp in stamps[1:]:
        dt_hours = (stamp - prev).total_seconds() / 3600.0
        prev = stamp
        if dt_hours <= 0:
            continue
        points.append(
            HistoryPoint(
                dt_hours=dt_hours,
                voltage=_latest(voltage, stamp),
                current=_latest(current, stamp),
                charge_power=_latest(charge, stamp),
                discharge_power=_latest(discharge, stamp),
                temperature=_latest(temp, stamp),
            )
        )
    return points


async def async_get_history_points(hass: HomeAssistant, entities: dict[str, str | None], minutes: int) -> list[HistoryPoint]:
    entity_ids = [entity_id for entity_id in entities.values() if entity_id]
    if not entity_ids or minutes <= 0:
        return []

    end_time = dt_util.utcnow()
    start_time = end_time - timedelta(minutes=minutes)

    def fetch():
        return get_significant_states(hass, start_time, end_time, entity_ids, False, False)

    try:
        raw = await hass.async_add_executor_job(fetch)
    except RuntimeError:
        return []

    return build_history_points(raw, entities)
