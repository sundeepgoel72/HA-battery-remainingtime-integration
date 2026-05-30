"""Algorithm comparison helpers."""

from __future__ import annotations

from .const import ALGORITHMS
from .predictor import BatteryInputs, BatteryPrediction, predict


def clone_inputs(inputs: BatteryInputs, algorithm: str) -> BatteryInputs:
    """Clone inputs with a different algorithm name."""
    return BatteryInputs(
        algorithm=algorithm,
        capacity_ah=inputs.capacity_ah,
        nominal_voltage=inputs.nominal_voltage,
        voltage=inputs.voltage,
        current=inputs.current,
        charge_power=inputs.charge_power,
        discharge_power=inputs.discharge_power,
        temperature=inputs.temperature,
        history_window_minutes=inputs.history_window_minutes,
        peukert_exponent=inputs.peukert_exponent,
        charge_efficiency=inputs.charge_efficiency,
        internal_resistance_ohm=inputs.internal_resistance_ohm,
        kibam_c=inputs.kibam_c,
        kibam_k=inputs.kibam_k,
        previous_soc_percent=inputs.previous_soc_percent,
        history=inputs.history,
    )


def predict_all(inputs: BatteryInputs) -> dict[str, BatteryPrediction]:
    """Run all configured algorithms."""
    return {algorithm: predict(clone_inputs(inputs, algorithm)) for algorithm in ALGORITHMS}
