"""Battery prediction algorithms for lead-acid batteries.

The models here are intentionally dependency-free so the integration can run inside
Home Assistant without external Python packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, isfinite, log

from .const import (
    ALGORITHM_ADAPTIVE_HYBRID,
    ALGORITHM_CURRENT_FLOW,
    ALGORITHM_HYBRID_LEAD_ACID,
    ALGORITHM_POWER_FLOW,
    ALGORITHM_VOLTAGE_ONLY,
    MODE_CHARGING,
    MODE_DISCHARGING,
    MODE_IDLE,
    MODE_UNKNOWN,
)

ALGORITHM_TEMPERATURE = "temperature_compensated"
ALGORITHM_PEUCKERT = "peukert"
ALGORITHM_KIBAM = "kibam"
ALGORITHM_SHEPHERD = "shepherd"
ALGORITHM_ENSEMBLE = "ensemble"


@dataclass(slots=True)
class HistoryPoint:
    """Single historical point.

    dt_hours is the elapsed time since the previous point.
    """

    dt_hours: float
    voltage: float | None = None
    current: float | None = None
    charge_power: float | None = None
    discharge_power: float | None = None
    temperature: float | None = None


@dataclass(slots=True)
class BatteryInputs:
    """Current and recent battery readings."""

    algorithm: str
    capacity_ah: float
    nominal_voltage: float
    voltage: float | None = None
    current: float | None = None
    charge_power: float | None = None
    discharge_power: float | None = None
    temperature: float | None = None
    history_window_minutes: int = 60
    peukert_exponent: float = 1.20
    charge_efficiency: float = 0.85
    internal_resistance_ohm: float = 0.02
    kibam_c: float = 0.60
    kibam_k: float = 0.15
    previous_soc_percent: float | None = None
    history: list[HistoryPoint] = field(default_factory=list)


@dataclass(slots=True)
class BatteryPrediction:
    """Computed battery forecast."""

    algorithm: str
    soc_percent: float | None
    mode: str
    net_power_w: float | None
    time_to_empty_h: float | None
    time_to_full_h: float | None
    confidence: str
    reason: str


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value."""
    return max(low, min(high, value))


def safe_round(value: float | None, digits: int = 2) -> float | None:
    """Round finite values only."""
    if value is None or not isfinite(value):
        return None
    return round(value, digits)


# Approximate rested open-circuit voltage curve for 12V lead-acid.
OCV_12V_POINTS: tuple[tuple[float, float], ...] = (
    (11.80, 0.0),
    (11.90, 10.0),
    (12.00, 20.0),
    (12.10, 30.0),
    (12.20, 40.0),
    (12.30, 50.0),
    (12.40, 60.0),
    (12.50, 70.0),
    (12.60, 80.0),
    (12.70, 90.0),
    (12.80, 100.0),
)


def estimate_soc_ocv(voltage: float | None, nominal_voltage: float) -> float | None:
    """Estimate state of charge from rested open-circuit voltage."""
    if voltage is None or nominal_voltage <= 0:
        return None
    scaled = voltage * 12.0 / nominal_voltage
    points = OCV_12V_POINTS
    if scaled <= points[0][0]:
        return points[0][1]
    if scaled >= points[-1][0]:
        return points[-1][1]
    for (v1, s1), (v2, s2) in zip(points, points[1:], strict=True):
        if v1 <= scaled <= v2:
            return s1 + ((scaled - v1) / (v2 - v1)) * (s2 - s1)
    return None


def temperature_capacity_factor(temp_c: float | None) -> float:
    """Approximate lead-acid usable capacity factor by temperature."""
    if temp_c is None:
        return 1.0
    if temp_c <= -20:
        return 0.50
    if temp_c <= 0:
        return 0.75
    if temp_c <= 10:
        return 0.85
    if temp_c <= 20:
        return 0.95
    if temp_c <= 35:
        return 1.0
    return 0.95


def resolve_net_power(inputs: BatteryInputs) -> tuple[float | None, str]:
    """Resolve net power; positive charging, negative discharging.

    Signed battery current is preferred because it directly describes charge
    direction. Charge/discharge power sensors are fallback inputs for systems
    that do not expose battery current.
    """
    if inputs.current is not None and inputs.voltage is not None:
        return float(inputs.current) * float(inputs.voltage), "current x voltage"
    if inputs.charge_power is not None or inputs.discharge_power is not None:
        charge = max(float(inputs.charge_power or 0.0), 0.0)
        discharge = max(float(inputs.discharge_power or 0.0), 0.0)
        return charge - discharge, "charge/discharge power fallback"
    return None, "missing power/current"


def mode_from_power(net_power: float | None) -> str:
    """Convert net power to battery mode."""
    if net_power is None:
        return MODE_UNKNOWN
    if net_power > 10:
        return MODE_CHARGING
    if net_power < -10:
        return MODE_DISCHARGING
    return MODE_IDLE


def capacity_wh(inputs: BatteryInputs, temperature_adjusted: bool = False) -> float:
    """Rated or temperature-adjusted capacity in Wh."""
    factor = temperature_capacity_factor(inputs.temperature) if temperature_adjusted else 1.0
    return max(inputs.capacity_ah * inputs.nominal_voltage * factor, 0.0)


def runtime_from_soc(inputs: BatteryInputs, soc: float | None, net_power: float | None, *, peukert: bool = False, temp: bool = False) -> tuple[float | None, float | None]:
    """Compute time to empty/full from SoC and net power."""
    if soc is None or net_power is None:
        return None, None
    mode = mode_from_power(net_power)
    cap_wh = capacity_wh(inputs, temperature_adjusted=temp)
    remaining_wh = cap_wh * clamp(soc, 0, 100) / 100
    missing_wh = cap_wh - remaining_wh
    if mode == MODE_DISCHARGING:
        discharge_w = abs(net_power)
        if peukert and inputs.nominal_voltage > 0:
            amps = discharge_w / inputs.nominal_voltage
            rated_current = max(inputs.capacity_ah / 20.0, 0.1)  # common C20 rating
            factor = (rated_current / max(amps, 0.1)) ** max(inputs.peukert_exponent - 1.0, 0.0)
            remaining_wh *= clamp(factor, 0.25, 1.2)
        return remaining_wh / discharge_w if discharge_w > 1 else None, None
    if mode == MODE_CHARGING:
        return None, missing_wh / (net_power * max(inputs.charge_efficiency, 0.1)) if net_power > 1 else None
    return None, None


def voltage_ocv(inputs: BatteryInputs) -> BatteryPrediction:
    """Voltage lookup model."""
    soc = estimate_soc_ocv(inputs.voltage, inputs.nominal_voltage)
    net, src = resolve_net_power(inputs)
    tte, ttf = runtime_from_soc(inputs, soc, net)
    return _prediction(ALGORITHM_VOLTAGE_ONLY, soc, net, tte, ttf, "medium" if soc is not None else "low", f"OCV lookup; {src}")


def current_flow(inputs: BatteryInputs) -> BatteryPrediction:
    """Coulomb counting over supplied history, anchored by previous or OCV SoC."""
    soc = inputs.previous_soc_percent if inputs.previous_soc_percent is not None else estimate_soc_ocv(inputs.voltage, inputs.nominal_voltage)
    if soc is None:
        soc = 50.0
        confidence = "low"
        reason = "no OCV/previous SoC; using 50% seed"
    else:
        confidence = "medium"
        reason = "coulomb counting anchored by OCV/previous SoC"
    amp_hours = 0.0
    for p in inputs.history:
        if p.current is not None and p.dt_hours > 0:
            current = p.current * (inputs.charge_efficiency if p.current > 0 else 1.0)
            amp_hours += current * p.dt_hours
    if inputs.current is not None and not inputs.history:
        amp_hours += inputs.current * (inputs.history_window_minutes / 60.0) * (inputs.charge_efficiency if inputs.current > 0 else 1.0)
        reason += "; approximated from current reading"
        confidence = "low"
    soc = clamp(soc + (amp_hours / max(inputs.capacity_ah, 0.1)) * 100.0, 0, 100)
    net, src = resolve_net_power(inputs)
    tte, ttf = runtime_from_soc(inputs, soc, net)
    return _prediction(ALGORITHM_CURRENT_FLOW, soc, net, tte, ttf, confidence, f"{reason}; {src}")


def power_flow(inputs: BatteryInputs) -> BatteryPrediction:
    """Energy integration model over power readings."""
    soc = inputs.previous_soc_percent if inputs.previous_soc_percent is not None else estimate_soc_ocv(inputs.voltage, inputs.nominal_voltage)
    if soc is None:
        soc = 50.0
        confidence = "low"
    else:
        confidence = "medium"
    wh = 0.0
    for p in inputs.history:
        if p.current is not None and p.voltage is not None:
            current_power = p.current * p.voltage
            wh += current_power * (inputs.charge_efficiency if current_power > 0 else 1.0) * p.dt_hours
            continue
        charge = max(p.charge_power or 0, 0)
        discharge = max(p.discharge_power or 0, 0)
        if charge or discharge:
            wh += (charge * inputs.charge_efficiency - discharge) * p.dt_hours
    net, src = resolve_net_power(inputs)
    if not inputs.history and net is not None:
        wh += net * (inputs.history_window_minutes / 60.0)
        confidence = "low"
    cap = max(capacity_wh(inputs), 0.1)
    soc = clamp(soc + (wh / cap) * 100.0, 0, 100)
    tte, ttf = runtime_from_soc(inputs, soc, net)
    return _prediction(ALGORITHM_POWER_FLOW, soc, net, tte, ttf, confidence, f"energy integration; {src}")
