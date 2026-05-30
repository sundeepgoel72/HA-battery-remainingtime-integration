"""Battery operating state and calibration-evidence event detection."""

from __future__ import annotations

from dataclasses import dataclass

from .predictor import BatteryInputs, BatteryPrediction

STATE_UNKNOWN = "unknown"
STATE_RESTING = "resting"
STATE_CHARGING = "charging"
STATE_DISCHARGING = "discharging"
STATE_FLOAT = "float"
STATE_ABSORPTION = "absorption"
STATE_LOW_BATTERY = "low_battery"
STATE_HEAVY_DISCHARGE = "heavy_discharge"


@dataclass(slots=True)
class BatteryEventState:
    """Detected battery operating state."""

    state: str
    evidence: list[str]
    calibration_anchor: bool = False


def detect_event_state(inputs: BatteryInputs, prediction: BatteryPrediction) -> BatteryEventState:
    """Detect useful battery states for diagnostics and future calibration."""
    evidence: list[str] = []
    voltage = inputs.voltage
    current = inputs.current
    net_power = prediction.net_power_w
    soc = prediction.soc_percent

    if voltage is None:
        return BatteryEventState(STATE_UNKNOWN, ["missing_voltage"])

    nominal = max(inputs.nominal_voltage, 1.0)
    normalized_voltage = voltage * 12.0 / nominal

    if current is not None and abs(current) <= max(inputs.capacity_ah * 0.01, 1.0):
        evidence.append("current_near_zero")
        if inputs.history:
            recent_voltages = [p.voltage for p in inputs.history[-5:] if p.voltage is not None]
            if len(recent_voltages) >= 2 and max(recent_voltages) - min(recent_voltages) <= nominal * 0.002:
                evidence.append("voltage_stable")
                return BatteryEventState(STATE_RESTING, evidence, calibration_anchor=True)
        return BatteryEventState(STATE_RESTING, evidence)

    if soc is not None and soc <= 15:
        evidence.append("soc_below_15")
        return BatteryEventState(STATE_LOW_BATTERY, evidence, calibration_anchor=True)

    if net_power is not None and net_power < 0:
        discharge_rate_c = abs(net_power) / max(inputs.capacity_ah * inputs.nominal_voltage, 1.0)
        evidence.append("net_power_negative")
        if discharge_rate_c >= 0.20:
            evidence.append("discharge_rate_above_c20")
            return BatteryEventState(STATE_HEAVY_DISCHARGE, evidence)
        return BatteryEventState(STATE_DISCHARGING, evidence)

    if net_power is not None and net_power > 0:
        evidence.append("net_power_positive")
        if normalized_voltage >= 14.2:
            evidence.append("high_charge_voltage")
            return BatteryEventState(STATE_ABSORPTION, evidence, calibration_anchor=True)
        if normalized_voltage >= 13.4 and current is not None and current <= max(inputs.capacity_ah * 0.03, 2.0):
            evidence.append("float_voltage_and_low_current")
            return BatteryEventState(STATE_FLOAT, evidence, calibration_anchor=True)
        return BatteryEventState(STATE_CHARGING, evidence)

    return BatteryEventState(STATE_UNKNOWN, evidence or ["insufficient_signal"])
