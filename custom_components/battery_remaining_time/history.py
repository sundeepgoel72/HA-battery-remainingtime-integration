"""Recorder history helpers for Battery Remaining Time."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from .predictor import HistoryPoint

_LOGGER = logging.getLogger(__name__)


def _float_state(state: Any | None) -> float | None:
    """Return a numeric state value when possible."""
    if state is None or state.state in {"unknown", "unavailable"}:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _time(state: Any):
    """Return the best timestamp available on a state object."""
    return getattr(state, "last_updated", None) or getattr(state, "last_changed", None)


def _latest(states: list[Any], when) -> float | None:
    """Return latest value at or before a timestamp."""
    selected = None
    for state in states:
        stamp = _time(state)
        if stamp is not None and stamp <= when:
            selected = state
        elif stamp is not None:
            break
    return _float_state(selected or (states[0] if states else None))


def _normalize_raw_history(raw: Any, entity_ids: list[str]) -> dict[str, list[Any]]:
    """Normalize recorder history output to entity_id -> states.

    Home Assistant recorder helpers have returned both dict and list shapes
    across versions. Supporting both keeps the integration compatible.
    """
    if isinstance(raw, dict):
        return {entity_id: list(raw.get(entity_id, [])) for entity_id in entity_ids}
    if isinstance(raw, list):
        normalized: dict[str, list[Any]] = {entity_id: [] for entity_id in entity_ids}
        for item in raw:
            if not item:
                continue
            if isinstance(item, list):
                for state in item:
                    entity_id = getattr(state, "entity_id", None)
                    if entity_id in normalized:
                        normalized[entity_id].append(state)
            else:
                entity_id = getattr(item, "entity_id", None)
                if entity_id in normalized:
                    normalized[entity_id].append(item)
        return normalized
    return {entity_id: [] for entity_id in entity_ids}


def build_history_points(raw: dict[str, list[Any]], entities: dict[str, str | None]) -> list[HistoryPoint]:
    """Convert recorder state rows into model history points."""
    voltage = raw.get(entities.get("voltage") or "", [])
    current = raw.get(entities.get("current") or "", [])
    charge = raw.get(entities.get("charge_power") or "", [])
    discharge = raw.get(entities.get("discharge_power") or "", [])
    temp = raw.get(entities.get("temperature") or "", [])

    stamps = sorted({_time(s) for states in raw.values() for s in states if _time(s) is not None})
    _LOGGER.debug(
        "Recorder raw state counts: voltage=%s current=%s charge=%s discharge=%s temperature=%s timestamps=%s",
        len(voltage),
        len(current),
        len(charge),
        len(discharge),
        len(temp),
        len(stamps),
    )
    if len(stamps) < 2:
        _LOGGER.debug("Not enough recorder timestamps to build history points")
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
                timestamp=stamp,
            )
        )
    _LOGGER.debug("Built %s battery history points from recorder", len(points))
    return points


def history_start_time(minutes: int, since: datetime | None = None) -> datetime:
    """Return recorder start time for a window, optionally bounded by a checkpoint."""
    window_start = dt_util.utcnow() - timedelta(minutes=minutes)
    if since is None:
        return window_start
    return max(window_start, since)


async def async_get_history_points(
    hass: Any,
    entities: dict[str, str | None],
    minutes: int,
    since: datetime | None = None,
) -> list[HistoryPoint]:
    """Fetch recent recorder history and convert it into HistoryPoint objects."""
    entity_ids = [entity_id for entity_id in entities.values() if entity_id]
    if not entity_ids or minutes <= 0:
        _LOGGER.debug("Skipping recorder history fetch: entity_ids=%s minutes=%s", entity_ids, minutes)
        return []

    end_time = dt_util.utcnow()
    start_time = history_start_time(minutes, since)
    _LOGGER.debug("Fetching recorder history for %s over %s minutes", entity_ids, minutes)
    from homeassistant.components import recorder
    from homeassistant.components.recorder.history import get_significant_states

    def fetch():
        return get_significant_states(
            hass,
            start_time,
            end_time,
            entity_ids,
            significant_changes_only=False,
            minimal_response=False,
        )

    try:
        recorder_instance = recorder.get_instance(hass)
        raw = await recorder_instance.async_add_executor_job(fetch)
    except Exception:
        _LOGGER.warning("Recorder history fetch failed", exc_info=True)
        return []

    normalized = _normalize_raw_history(raw, entity_ids)
    return build_history_points(normalized, entities)
