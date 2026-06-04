# Battery Remaining Time for Home Assistant

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).

Battery Remaining Time is a Home Assistant custom integration that estimates battery State of Charge (SOC), Time To Empty (TTE), and Time To Full (TTF) for lead-acid battery systems using Home Assistant sensor data and Recorder history.

The project is designed as a self-calibrating battery prediction engine that improves accuracy over time by collecting evidence from real-world battery behaviour.

Local development is intentionally narrower than a full Home Assistant runtime.

- Use the local `.venv` for unit tests, import checks, and linting.
- Use the live Home Assistant instance for config flow walkthroughs, entity verification, Recorder-backed behaviour, and end-to-end functional checks.

## Overview

The integration combines live sensor data, Recorder history, battery models, event detection, and calibration evidence to produce battery forecasts and confidence metrics.

Typical inputs include:

- Battery voltage
- Battery current
- Charge power
- Discharge power
- Battery temperature

The integration degrades gracefully when some sensors are unavailable.

## How It Works

1. Home Assistant entities provide battery telemetry.
2. Recorder history is analysed when available, but local tests keep that path lazy and isolated.
3. Battery operating state is detected.
4. Multiple prediction algorithms estimate SOC, TTE and TTF.
5. Calibration evidence is collected from observed battery behaviour.
6. Confidence scores are generated.
7. The selected algorithm result is exposed as Home Assistant entities together with per-algorithm comparison sensors and prediction diagnostics.

### Recorder History Usage

Recorder history is used to:

- Estimate charge rates
- Estimate discharge rates
- Detect long-term trends
- Improve calibration quality
- Detect anchor events

Recommended history window: 24 hours.

### Event Detection

Current event states:

- resting
- charging
- discharging
- float
- absorption
- low_battery
- heavy_discharge
- unknown

## Features

- Config Flow support
- Recorder history integration
- Multiple battery estimation algorithms
- Calibration evidence collection
- Persistent statistics
- Adaptive Peukert exponent learning
- Runtime profile optimization from learned capacity and charge efficiency
- Prediction diagnostics
- Home Assistant diagnostics download support
- Local-only operation
- HACS compatible

## Supported Algorithms

The integration supports multiple prediction approaches including:

- Voltage OCV
- Coulomb Counting
- Power Flow
- Peukert
- Hybrid
- Temperature Corrected
- KiBaM
- Shepherd
- Adaptive
- Ensemble

See docs/ALGORITHMS.md for details.

## Supported Battery Types

- Flooded Lead Acid
- Tubular Lead Acid
- AGM
- Gel
- Lead Carbon
- Custom Profiles (planned)

See docs/BATTERY_TYPES.md for details.

## Diagnostics

Diagnostic entities include:

- prediction_health
- calibration_status
- algorithm_spread
- model_accuracy
- prediction_confidence
- active_algorithm
- usable_soc
- time_to_depletion
- configured_depletion_voltage
- learned_depletion_voltage
- depletion_voltage_confidence
- learned_peukert_exponent
- peukert_confidence
- peukert_observation_count

Diagnostics expose confidence, algorithm selection, event state, calibration readiness, history window and calibration evidence.
They also expose profile-optimization and ageing details such as effective capacity, effective charge efficiency, estimated ageing rate, and model-accuracy convergence.
The usable-SOC path adds depletion-voltage diagnostics so flooded lead-acid systems can use practical cutoff values without bundling later chemistry-learning work.

Comparison sensors are exposed during the current beta field-validation phase so model divergence is immediately visible:

- `soc_ocv`, `soc_coulomb`, `soc_peukert`, `soc_hybrid`, `soc_ensemble`
- `tte_ocv`, `tte_coulomb`, `tte_peukert`, `tte_hybrid`, `tte_ensemble`
- `ttf_ocv`, `ttf_coulomb`, `ttf_peukert`, `ttf_hybrid`, `ttf_ensemble`

Coordinator debug logs also emit per-algorithm values and spread/confidence telemetry on every forecast update.

Home Assistant diagnostics support is included for config-entry troubleshooting. It redacts configured entity IDs and the battery name before export.

## Architecture

Sensors → Recorder History → Event Detection → Prediction Models → Calibration Engine → Confidence Engine → Home Assistant Entities

For a detailed description see docs/ARCHITECTURE.md.

## Documentation

- docs/ALGORITHMS.md
- docs/BATTERY_TYPES.md
- docs/CALIBRATION.md
- docs/ARCHITECTURE.md
- docs/adaptive-peukert-learning.md
- docs/RECORDER_BENCHMARKING.md
- docs/SCREENSHOTS.md
- BETA_RELEASE_PLAN.md

## Installation

Add the repository to HACS as a custom repository:

https://github.com/sundeepgoel72/HA-battery-remainingtime-integration

## Local Development

The local test surface is intentionally focused on high-level checks:

- `compileall`
- `ruff`
- `pytest`
- import safety for integration modules

Run the local suite with:

```bash
cd <repo-dir>
source .venv/bin/activate
python -m pytest -q
```

Keep Recorder-backed functional validation in the live Home Assistant instance.

## Beta Readiness

The current beta surface includes:

- HACS-compatible metadata and config flow
- Stable config-entry identity
- Home Assistant Repairs issue for missing source sensors
- Home Assistant diagnostics download support with redaction
- Comparison sensors and spread/confidence diagnostics for field debugging
- Robust median ensemble aggregation
- Spread-based confidence grading
- SOC rate limiting and last-valid-SOC preservation

Still pending before a public beta claim is closed:

- live field validation that the new ensemble hardening prevents idle-SOC collapse
- UI screenshots captured from the live Home Assistant frontend
- broader live-database recorder benchmarking beyond the current synthetic baseline

## MVP 2 Validation Checklist

Use the live Home Assistant instance to validate the following in order:

1. Main forecast: `estimated_soc`, `time_to_empty`, `time_to_full`, `confidence`, `algorithm`
2. Diagnostics: `prediction_health`, `calibration_status`, `algorithm_spread`, `prediction_confidence`, `active_algorithm`
3. Comparison sensors: `soc_*`, `tte_*`, and `ttf_*` outputs for divergence and outliers
4. Stability: confirm the forecast does not collapse to synthetic `0%` under idle or weak-source conditions
5. Release imagery: capture the screenshot set in `docs/SCREENSHOTS.md`

## Roadmap

Phase 1

- Field validation
- Accuracy testing

Phase 2

- Comparison sensors and observability refinement
- Model divergence metrics

Phase 3

- Adaptive learning
- Capacity learning
- Charge efficiency learning

Phase 4

- Battery ageing estimation
- Profile optimization
- Longer-term field calibration

## Project Goal

Create a self-calibrating lead-acid battery prediction engine for Home Assistant that becomes more accurate through real-world battery observations.
