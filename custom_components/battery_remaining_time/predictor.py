"""Battery prediction algorithms for lead-acid batteries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from statistics import median
from typing import Callable

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
CONFIDENCE_ORDER = {
    "high": 4,
    "medium": 3,
    "low": 2,
    "very_low": 1,
}


@dataclass(slots=True)
class HistoryPoint:
    """Single historical point."""

    dt_hours: float
    voltage: float | None = None
    current: float | None = None
    charge_power: float | None = None
    discharge_power: float | None = None
    temperature: float | None = None
    timestamp: datetime | None = None


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
    depletion_voltage: float | None = None
    history_window_minutes: int = 60
    peukert_exponent: float = 1.20
    charge_efficiency: float = 0.85
    internal_resistance_ohm: float = 0.02
    kibam_c: float = 0.60
    kibam_k: float = 0.15
    previous_soc_percent: float | None = None
    history: list[HistoryPoint] = field(default_factory=list)
    model_accuracy: dict[str, float] = field(default_factory=dict)


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
    usable_soc_percent: float | None = None
    time_to_depletion_h: float | None = None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_round(value: float | None, digits: int = 2) -> float | None:
    if value is None or not isfinite(value):
        return None
    return round(value, digits)


def prediction_to_telemetry(prediction: BatteryPrediction) -> dict[str, float | str | None]:
    """Return a compact serializable representation for logs/attributes."""
    return {
        "soc_percent": prediction.soc_percent,
        "usable_soc_percent": prediction.usable_soc_percent,
        "mode": prediction.mode,
        "net_power_w": prediction.net_power_w,
        "time_to_empty_h": prediction.time_to_empty_h,
        "time_to_depletion_h": prediction.time_to_depletion_h,
        "time_to_full_h": prediction.time_to_full_h,
        "confidence": prediction.confidence,
        "reason": prediction.reason,
    }


def is_valid_soc(value: float | None) -> bool:
    """Return true when a SOC value is finite and in-range."""
    return value is not None and isfinite(value) and 0.0 <= value <= 100.0


def confidence_from_spread(spread: float | None, valid_model_count: int) -> str:
    """Return the confidence bucket implied by model agreement."""
    if valid_model_count < 2 or spread is None:
        return "low"
    if spread <= 5.0:
        return "high"
    if spread <= 15.0:
        return "medium"
    if spread <= 30.0:
        return "low"
    return "very_low"


def lower_confidence(*values: str) -> str:
    """Return the most conservative confidence level."""
    ranked = sorted((value for value in values if value), key=lambda value: CONFIDENCE_ORDER.get(value, 0))
    return ranked[0] if ranked else "low"


def algorithm_spread(predictions: dict[str, BatteryPrediction]) -> float | None:
    """Return max-min SOC spread across models."""
    values = [p.soc_percent for p in predictions.values() if is_valid_soc(p.soc_percent)]
    if len(values) < 2:
        return None
    return safe_round(max(values) - min(values), 1)


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


def practical_usable_soc(inputs: BatteryInputs, soc: float | None) -> float | None:
    """Return usable SOC above the configured depletion/cutoff voltage.

    This is operational SOC for inverter users. It intentionally does not replace
    battery SOC because the battery may have chemical capacity remaining below an
    inverter's trip voltage.
    """
    if soc is None:
        return None
    if inputs.depletion_voltage is None or inputs.depletion_voltage <= 0 or inputs.voltage is None:
        return soc
    if inputs.voltage <= inputs.depletion_voltage:
        return 0.0
    full_voltage = max(inputs.nominal_voltage * (12.8 / 12.0), inputs.depletion_voltage + 0.1)
    if inputs.voltage >= full_voltage:
        return min(soc, 100.0)
    voltage_usable = ((inputs.voltage - inputs.depletion_voltage) / (full_voltage - inputs.depletion_voltage)) * 100.0
    return clamp(min(soc, voltage_usable), 0.0, 100.0)


def time_to_depletion(inputs: BatteryInputs, usable_soc: float | None, net_power: float | None, *, peukert: bool = False, temp: bool = False) -> float | None:
    """Return runtime until practical depletion/cutoff voltage is reached."""
    if usable_soc is None or net_power is None or mode_from_power(net_power) != MODE_DISCHARGING:
        return None
    cap_wh = capacity_wh(inputs, temperature_adjusted=temp)
    remaining_wh = cap_wh * clamp(usable_soc, 0, 100) / 100
    discharge_w = abs(net_power)
    if peukert and inputs.nominal_voltage > 0:
        amps = discharge_w / inputs.nominal_voltage
        rated_current = max(inputs.capacity_ah / 20.0, 0.1)
        factor = (rated_current / max(amps, 0.1)) ** max(inputs.peukert_exponent - 1.0, 0.0)
        remaining_wh *= clamp(factor, 0.25, 1.2)
    return remaining_wh / discharge_w if discharge_w > 1 else None


def temperature_capacity_factor(temp_c: float | None) -> float:
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

    Signed current is preferred. Charge/discharge power sensors are fallback only.
    """
    if inputs.current is not None and inputs.voltage is not None:
        return float(inputs.current) * float(inputs.voltage), "current x voltage"
    if inputs.charge_power is not None or inputs.discharge_power is not None:
        charge = max(float(inputs.charge_power or 0.0), 0.0)
        discharge = max(float(inputs.discharge_power or 0.0), 0.0)
        return charge - discharge, "charge/discharge power fallback"
    return None, "missing power/current"


def mode_from_power(net_power: float | None) -> str:
    if net_power is None:
        return MODE_UNKNOWN
    if net_power > 10:
        return MODE_CHARGING
    if net_power < -10:
        return MODE_DISCHARGING
    return MODE_IDLE


def capacity_wh(inputs: BatteryInputs, temperature_adjusted: bool = False) -> float:
    factor = temperature_capacity_factor(inputs.temperature) if temperature_adjusted else 1.0
    return max(inputs.capacity_ah * inputs.nominal_voltage * factor, 0.0)


def runtime_from_soc(
    inputs: BatteryInputs,
    soc: float | None,
    net_power: float | None,
    *,
    peukert: bool = False,
    temp: bool = False,
) -> tuple[float | None, float | None]:
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
            rated_current = max(inputs.capacity_ah / 20.0, 0.1)
            factor = (rated_current / max(amps, 0.1)) ** max(inputs.peukert_exponent - 1.0, 0.0)
            remaining_wh *= clamp(factor, 0.25, 1.2)
        return remaining_wh / discharge_w if discharge_w > 1 else None, None
    if mode == MODE_CHARGING:
        return None, missing_wh / (net_power * max(inputs.charge_efficiency, 0.1)) if net_power > 1 else None
    return None, None


def voltage_ocv(inputs: BatteryInputs) -> BatteryPrediction:
    soc = estimate_soc_ocv(inputs.voltage, inputs.nominal_voltage)
    net, src = resolve_net_power(inputs)
    tte, ttf = runtime_from_soc(inputs, soc, net)
    return _prediction(ALGORITHM_VOLTAGE_ONLY, soc, net, tte, ttf, "medium" if soc is not None else "low", f"OCV lookup; {src}")


def current_flow(inputs: BatteryInputs) -> BatteryPrediction:
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
    soc = inputs.previous_soc_percent if inputs.previous_soc_percent is not None else estimate_soc_ocv(inputs.voltage, inputs.nominal_voltage)
    if soc is None:
        soc = 50.0
        confidence = "low"
    else:
        confidence = "medium"
    wh = 0.0
    for p in inputs.history:
        if p.current is not None and p.voltage is not None:
            power = p.current * p.voltage
            wh += power * (inputs.charge_efficiency if power > 0 else 1.0) * p.dt_hours
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


def peukert_model(inputs: BatteryInputs) -> BatteryPrediction:
    soc = inputs.previous_soc_percent if inputs.previous_soc_percent is not None else estimate_soc_ocv(inputs.voltage, inputs.nominal_voltage)
    net, src = resolve_net_power(inputs)
    tte, ttf = runtime_from_soc(inputs, soc, net, peukert=True)
    conf = "medium" if soc is not None and net is not None else "low"
    return _prediction(ALGORITHM_PEUCKERT, soc, net, tte, ttf, conf, f"Peukert exponent {inputs.peukert_exponent}; {src}")


def hybrid_ocv_coulomb(inputs: BatteryInputs) -> BatteryPrediction:
    ocv = voltage_ocv(inputs).soc_percent
    cc = current_flow(inputs).soc_percent if inputs.current is not None or inputs.history else None
    pf = power_flow(inputs).soc_percent if inputs.current is not None or inputs.charge_power is not None or inputs.discharge_power is not None or inputs.history else None
    weighted = [(v, w) for v, w in [(ocv, 0.35), (cc, 0.40), (pf, 0.25)] if v is not None]
    soc = sum(v * w for v, w in weighted) / sum(w for _, w in weighted) if weighted else None
    net, src = resolve_net_power(inputs)
    tte, ttf = runtime_from_soc(inputs, soc, net, peukert=True)
    conf = "high" if len(weighted) >= 2 and net is not None else "medium" if weighted else "low"
    return _prediction(ALGORITHM_HYBRID_LEAD_ACID, soc, net, tte, ttf, conf, f"weighted OCV/coulomb/power; {src}")


def temperature_compensated(inputs: BatteryInputs) -> BatteryPrediction:
    base = hybrid_ocv_coulomb(inputs)
    net, src = resolve_net_power(inputs)
    tte, ttf = runtime_from_soc(inputs, base.soc_percent, net, peukert=True, temp=True)
    conf = base.confidence if inputs.temperature is not None else "medium"
    return _prediction(ALGORITHM_TEMPERATURE, base.soc_percent, net, tte, ttf, conf, f"temperature capacity factor {temperature_capacity_factor(inputs.temperature):.2f}; {src}")


def kibam_model(inputs: BatteryInputs) -> BatteryPrediction:
    soc_seed = inputs.previous_soc_percent if inputs.previous_soc_percent is not None else estimate_soc_ocv(inputs.voltage, inputs.nominal_voltage)
    if soc_seed is None:
        soc_seed = 50.0
        confidence = "low"
    else:
        confidence = "medium"
    total_ah = inputs.capacity_ah * soc_seed / 100.0
    c = clamp(inputs.kibam_c, 0.05, 0.95)
    y1 = total_ah * c
    y2 = total_ah * (1 - c)
    steps = inputs.history or [HistoryPoint(inputs.history_window_minutes / 60.0, current=inputs.current, voltage=inputs.voltage)]
    for p in steps:
        current = p.current
        if current is None and p.charge_power is not None and p.voltage:
            current = p.charge_power / p.voltage
        if current is None and p.discharge_power is not None and p.voltage:
            current = -p.discharge_power / p.voltage
        if current is None:
            continue
        dt = max(p.dt_hours, 0)
        transfer = inputs.kibam_k * (y2 / max(1 - c, 0.01) - y1 / c) * dt
        y1 += transfer + current * dt
        y2 -= transfer
        y1 = clamp(y1, 0, inputs.capacity_ah * c)
        y2 = clamp(y2, 0, inputs.capacity_ah * (1 - c))
    soc = clamp(((y1 + y2) / max(inputs.capacity_ah, 0.1)) * 100, 0, 100)
    net, src = resolve_net_power(inputs)
    tte, ttf = runtime_from_soc(inputs, soc, net, peukert=True, temp=True)
    return _prediction(ALGORITHM_KIBAM, soc, net, tte, ttf, confidence, f"simplified KiBaM c={c:.2f}, k={inputs.kibam_k}; {src}")


def shepherd_model(inputs: BatteryInputs) -> BatteryPrediction:
    if inputs.voltage is None:
        return _prediction(ALGORITHM_SHEPHERD, None, None, None, None, "low", "missing voltage")
    current = inputs.current or 0.0
    corrected_v = inputs.voltage + current * inputs.internal_resistance_ohm
    soc = estimate_soc_ocv(corrected_v, inputs.nominal_voltage)
    net, src = resolve_net_power(inputs)
    tte, ttf = runtime_from_soc(inputs, soc, net, peukert=True, temp=True)
    return _prediction(ALGORITHM_SHEPHERD, soc, net, tte, ttf, "medium" if soc is not None else "low", f"Shepherd voltage inversion; {src}")


def adaptive_hybrid(inputs: BatteryInputs) -> BatteryPrediction:
    hybrid = temperature_compensated(inputs)
    soc = hybrid.soc_percent
    if soc is not None and inputs.history:
        voltages = [p.voltage for p in inputs.history if p.voltage is not None]
        if len(voltages) >= 3:
            slope = voltages[-1] - voltages[0]
            soc = clamp(soc + (slope * 12.0 / max(inputs.nominal_voltage, 1.0)) * 5.0, 0, 100)
    net, src = resolve_net_power(inputs)
    tte, ttf = runtime_from_soc(inputs, soc, net, peukert=True, temp=True)
    conf = "high" if inputs.history and hybrid.confidence != "low" else hybrid.confidence
    return _prediction(ALGORITHM_ADAPTIVE_HYBRID, soc, net, tte, ttf, conf, f"adaptive deterministic hybrid; {src}")


BASE_MODEL_FUNCTIONS: tuple[tuple[str, Callable[[BatteryInputs], BatteryPrediction]], ...] = (
    (ALGORITHM_VOLTAGE_ONLY, voltage_ocv),
    (ALGORITHM_CURRENT_FLOW, current_flow),
    (ALGORITHM_POWER_FLOW, power_flow),
    (ALGORITHM_PEUCKERT, peukert_model),
    (ALGORITHM_HYBRID_LEAD_ACID, hybrid_ocv_coulomb),
    (ALGORITHM_TEMPERATURE, temperature_compensated),
    (ALGORITHM_KIBAM, kibam_model),
    (ALGORITHM_SHEPHERD, shepherd_model),
    (ALGORITHM_ADAPTIVE_HYBRID, adaptive_hybrid),
)


def base_model_predictions(inputs: BatteryInputs) -> dict[str, BatteryPrediction]:
    """Run all non-ensemble models."""
    return {algorithm: fn(inputs) for algorithm, fn in BASE_MODEL_FUNCTIONS}


def _weighted_average(terms: list[tuple[float, float]]) -> float | None:
    """Return a weighted average from non-empty numeric terms."""
    total_weight = sum(weight for _, weight in terms)
    if total_weight <= 0:
        return None
    return sum(value * weight for value, weight in terms) / total_weight


def rebuild_prediction_with_soc(inputs: BatteryInputs, prediction: BatteryPrediction, soc: float, reason_suffix: str = "") -> BatteryPrediction:
    """Return one prediction rebuilt around a replacement SOC value."""
    use_peukert = prediction.algorithm in {
        ALGORITHM_PEUCKERT,
        ALGORITHM_HYBRID_LEAD_ACID,
        ALGORITHM_TEMPERATURE,
        ALGORITHM_KIBAM,
        ALGORITHM_SHEPHERD,
        ALGORITHM_ADAPTIVE_HYBRID,
        ALGORITHM_ENSEMBLE,
    }
    use_temp = prediction.algorithm in {
        ALGORITHM_TEMPERATURE,
        ALGORITHM_KIBAM,
        ALGORITHM_SHEPHERD,
        ALGORITHM_ADAPTIVE_HYBRID,
        ALGORITHM_ENSEMBLE,
    }
    tte, ttf = runtime_from_soc(inputs, soc, prediction.net_power_w, peukert=use_peukert, temp=use_temp)
    updated = _prediction(
        prediction.algorithm,
        soc,
        prediction.net_power_w,
        tte,
        ttf,
        prediction.confidence,
        f"{prediction.reason}{reason_suffix}",
    )
    return _apply_depletion_metrics(inputs, updated)


def _is_resting_like(inputs: BatteryInputs, net_power: float | None) -> bool:
    """Return true when live readings indicate idle/resting behaviour."""
    if net_power is not None and abs(net_power) <= 10.0:
        return True
    if inputs.current is not None and abs(inputs.current) <= max(inputs.capacity_ah * 0.005, 1.0):
        return True
    return False


def _resting_ocv_anchor_soc(predictions: dict[str, BatteryPrediction]) -> float | None:
    """Return authoritative resting SOC anchor from voltage-based models."""
    ocv = predictions.get(ALGORITHM_VOLTAGE_ONLY)
    shepherd = predictions.get(ALGORITHM_SHEPHERD)
    if ocv is None or ocv.soc_percent is None:
        return None

    anchor_terms: list[tuple[float, float]] = [(ocv.soc_percent, 0.65)]
    if shepherd is not None and shepherd.soc_percent is not None:
        anchor_terms.append((shepherd.soc_percent, 0.35))

    anchor = _weighted_average(anchor_terms)
    if anchor is None or anchor < 90.0:
        return None

    adaptive = predictions.get(ALGORITHM_ADAPTIVE_HYBRID)
    if adaptive is not None and adaptive.soc_percent is not None and abs(adaptive.soc_percent - anchor) <= 8.0:
        anchor_terms.append((adaptive.soc_percent, 0.15))
        anchor = _weighted_average(anchor_terms)

    return anchor


def _robust_soc_terms(inputs: BatteryInputs, predictions: dict[str, BatteryPrediction]) -> tuple[list[tuple[str, float]], float | None, bool]:
    """Return valid SOC terms, optional resting anchor, and whether anchor filtering was applied."""
    net, _ = resolve_net_power(inputs)
    resting = _is_resting_like(inputs, net)
    anchor_soc = _resting_ocv_anchor_soc(predictions) if resting else None
    terms = [
        (algorithm, float(prediction.soc_percent))
        for algorithm, prediction in predictions.items()
        if algorithm != ALGORITHM_ENSEMBLE and is_valid_soc(prediction.soc_percent)
    ]
    if anchor_soc is None:
        return terms, None, False

    anchor_algorithms = {
        ALGORITHM_VOLTAGE_ONLY,
        ALGORITHM_SHEPHERD,
        ALGORITHM_HYBRID_LEAD_ACID,
        ALGORITHM_TEMPERATURE,
        ALGORITHM_ADAPTIVE_HYBRID,
    }
    anchored_terms = [
        (algorithm, soc)
        for algorithm, soc in terms
        if algorithm in anchor_algorithms or abs(soc - anchor_soc) <= 20.0
    ]
    if len(anchored_terms) >= 2:
        return anchored_terms, anchor_soc, True
    return terms, anchor_soc, False


def _resting_weight_multiplier(algorithm: str) -> float:
    """Weight adjustment for non-full resting states."""
    return {
        ALGORITHM_VOLTAGE_ONLY: 4.0,
        ALGORITHM_SHEPHERD: 3.5,
        ALGORITHM_ADAPTIVE_HYBRID: 1.6,
        ALGORITHM_PEUCKERT: 1.2,
        ALGORITHM_HYBRID_LEAD_ACID: 1.0,
        ALGORITHM_TEMPERATURE: 1.0,
        ALGORITHM_CURRENT_FLOW: 0.35,
        ALGORITHM_POWER_FLOW: 0.35,
        ALGORITHM_KIBAM: 0.35,
    }.get(algorithm, 1.0)


def ensemble_model_weights(inputs: BatteryInputs, predictions: dict[str, BatteryPrediction]) -> dict[str, float]:
    """Return bounded normalized adaptive ensemble weights.

    Every model with a SOC estimate remains active. Learned accuracy can move a
    model up or down, but individual weights are capped so a single model cannot
    dominate the ensemble after a few calibration anchors.
    """
    net, _ = resolve_net_power(inputs)
    resting = _is_resting_like(inputs, net)
    confidence_weights = {"high": 1.0, "medium": 0.55, "low": 0.20}
    raw_weights: dict[str, float] = {}

    for algorithm, prediction in predictions.items():
        if algorithm == ALGORITHM_ENSEMBLE or prediction.soc_percent is None:
            continue

        confidence_weight = confidence_weights.get(prediction.confidence, 0.20)
        context_weight = _resting_weight_multiplier(algorithm) if resting else 1.0
        accuracy = inputs.model_accuracy.get(algorithm)
        accuracy_weight = 1.0
        if accuracy is not None:
            accuracy_weight = 0.50 + clamp(float(accuracy), 0.05, 1.0)

        raw_weights[algorithm] = clamp(confidence_weight * context_weight * accuracy_weight, 0.05, 4.0)

    return _normalize_capped_weights(raw_weights, max_weight=0.35, min_weight=0.02)


def ensemble_model_weighting_strategy(inputs: BatteryInputs, predictions: dict[str, BatteryPrediction]) -> dict[str, float | int | str | bool]:
    """Return diagnostic metadata describing adaptive ensemble weighting."""
    net, _ = resolve_net_power(inputs)
    active_models = [
        algorithm
        for algorithm, prediction in predictions.items()
        if algorithm != ALGORITHM_ENSEMBLE and prediction.soc_percent is not None
    ]
    return {
        "strategy": "adaptive_accuracy_bounded",
        "active_model_count": len(active_models),
        "accuracy_model_count": sum(1 for model in active_models if model in inputs.model_accuracy),
        "resting_context": _is_resting_like(inputs, net),
        "max_model_weight": 0.35,
        "min_model_weight": 0.02,
    }


def _normalize_capped_weights(raw_weights: dict[str, float], *, max_weight: float, min_weight: float) -> dict[str, float]:
    """Normalize model weights while keeping every model active and bounded."""
    if not raw_weights:
        return {}

    total = sum(max(weight, 0.0) for weight in raw_weights.values())
    if total <= 0:
        even_weight = round(1.0 / len(raw_weights), 4)
        return {model: even_weight for model in raw_weights}

    cap = max(max_weight, 1.0 / len(raw_weights))
    weights = {model: max(weight, 0.0) / total for model, weight in raw_weights.items()}

    capped_models: set[str] = set()
    for _ in range(len(weights)):
        over_cap = {model for model, weight in weights.items() if weight > cap and model not in capped_models}
        if not over_cap:
            break
        capped_models.update(over_cap)
        remaining_weight = max(1.0 - (len(capped_models) * cap), 0.0)
        flexible_models = [model for model in weights if model not in capped_models]
        flexible_total = sum(max(raw_weights[model], 0.0) for model in flexible_models)
        for model in capped_models:
            weights[model] = cap
        if flexible_total <= 0:
            continue
        for model in flexible_models:
            weights[model] = (max(raw_weights[model], 0.0) / flexible_total) * remaining_weight

    if len(weights) * min_weight < 1.0:
        low_models = {model for model, weight in weights.items() if weight < min_weight}
        if low_models:
            remaining_weight = max(1.0 - (len(low_models) * min_weight), 0.0)
            flexible_models = [model for model in weights if model not in low_models]
            flexible_total = sum(weights[model] for model in flexible_models)
            for model in low_models:
                weights[model] = min_weight
            if flexible_total > 0:
                for model in flexible_models:
                    weights[model] = (weights[model] / flexible_total) * remaining_weight

    return {model: round(weight, 4) for model, weight in sorted(weights.items())}


def _apply_depletion_metrics(inputs: BatteryInputs, prediction: BatteryPrediction) -> BatteryPrediction:
    """Populate practical usable SOC and time-to-depletion on one prediction."""
    usable = practical_usable_soc(inputs, prediction.soc_percent)
    prediction.usable_soc_percent = safe_round(usable, 1)
    prediction.time_to_depletion_h = safe_round(
        time_to_depletion(inputs, usable, prediction.net_power_w, peukert=True, temp=True), 2
    )
    return prediction


def ensemble_from_predictions(inputs: BatteryInputs, predictions: dict[str, BatteryPrediction]) -> BatteryPrediction:
    """Build ensemble result from already-computed model outputs."""
    net, src = resolve_net_power(inputs)
    terms, anchor_soc, anchor_filtered = _robust_soc_terms(inputs, predictions)
    learned_used = any(algorithm in inputs.model_accuracy for algorithm, _ in terms)
    soc_values = [soc for _, soc in terms]
    soc = median(soc_values) if soc_values else None
    spread = algorithm_spread(predictions)
    tte, ttf = runtime_from_soc(inputs, soc, net, peukert=True, temp=True)
    conf = confidence_from_spread(spread, len(terms))
    reason = f"robust median ensemble of {len(terms)} models; {src}"
    if anchor_soc is not None:
        reason += "; resting OCV/Shepherd anchor available"
    if anchor_filtered:
        reason += "; anchor-guided outlier rejection"
    if learned_used:
        reason += "; adaptive accuracy diagnostics active"
    return _prediction(ALGORITHM_ENSEMBLE, soc, net, tte, ttf, conf, reason)


def all_model_predictions(inputs: BatteryInputs) -> dict[str, BatteryPrediction]:
    """Run all models, including ensemble, for telemetry and diagnostics."""
    predictions = base_model_predictions(inputs)
    predictions[ALGORITHM_ENSEMBLE] = ensemble_from_predictions(inputs, predictions)
    for prediction in predictions.values():
        _apply_depletion_metrics(inputs, prediction)
    return predictions


def ensemble_model(inputs: BatteryInputs) -> BatteryPrediction:
    return all_model_predictions(inputs)[ALGORITHM_ENSEMBLE]


def predict(inputs: BatteryInputs) -> BatteryPrediction:
    predictions = all_model_predictions(inputs)
    return predictions.get(inputs.algorithm) or predictions[ALGORITHM_HYBRID_LEAD_ACID]


def _prediction(
    algorithm: str,
    soc: float | None,
    net: float | None,
    tte: float | None,
    ttf: float | None,
    confidence: str,
    reason: str,
) -> BatteryPrediction:
    return BatteryPrediction(
        algorithm=algorithm,
        soc_percent=safe_round(soc, 1),
        mode=mode_from_power(net),
        net_power_w=safe_round(net, 1),
        time_to_empty_h=safe_round(tte, 2),
        time_to_full_h=safe_round(ttf, 2),
        confidence=confidence,
        reason=reason,
    )
