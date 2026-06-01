# Adaptive Peukert Learning

Version: `0.1.1`

## What Changed

Battery Remaining Time now learns a Peukert exponent from real discharge evidence instead of relying only on the fixed default exponent.

The learner uses Home Assistant Recorder history and persistent integration storage. It observes sustained discharge windows, waits for a low-battery calibration anchor, compares the actual runtime against the predicted Peukert-adjusted runtime, and gradually updates a learned exponent.

The existing prediction algorithms remain intact. The learned exponent is only injected into the existing Peukert-capable algorithms after confidence reaches `medium`; while confidence is `low`, the integration continues to use the configured/default exponent.

## Learned Fields

The integration persists and exposes:

- `learned_peukert_exponent`
- `peukert_confidence`
- `peukert_observation_count`

These values are available as diagnostic statistics sensors and in relevant diagnostic attributes.

## Learning Inputs

A Peukert observation requires:

- Recorder history with a sustained discharge segment.
- Current or discharge-power evidence.
- Voltage evidence at the start of the discharge segment.
- A low-battery calibration anchor at the end of the observed cycle.
- Enough runtime and current difference from the 20-hour rated current to make the exponent meaningful.

The learner ignores short, incomplete, idle, charging, or ambiguous windows.

## Confidence Behaviour

Confidence is intentionally conservative:

- `low`: learned value is stored for diagnostics, but prediction still uses the default exponent.
- `medium`: learned value is used by Peukert-capable algorithms.
- `high`: learned value has accumulated more observations and continues to be smoothed.

This prevents a single bad discharge event from destabilizing runtime predictions.

## Usage

1. Configure voltage and either current or discharge-power sensors.
2. Keep Recorder enabled for those source sensors.
3. Let the system observe real discharge cycles until the battery reaches the configured low/depletion region.
4. Watch the diagnostic sensors:
   - `Learned Peukert exponent`
   - `Peukert confidence`
   - `Peukert observation count`
5. Treat the learned exponent as operationally useful once confidence reaches `medium` or `high`.

## Validation

Regression checks for this release:

- Python compile check.
- Ruff lint.
- Pytest unit suite with plugin autoload disabled.
- Local Home Assistant custom component update and container restart.

Focused tests cover:

- Low-confidence fallback to the default Peukert exponent.
- Medium-confidence use of the learned exponent.
- Diagnostic sensor registration for Peukert learning fields.
