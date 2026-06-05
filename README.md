# Battery Remaining Time for Home Assistant

Battery Remaining Time is a Home Assistant custom integration for lead-acid battery systems. It estimates battery state of charge, time to empty, and time to full from sensors you already expose in Home Assistant.

It is built for inverter, solar, UPS, and off-grid setups where the built-in battery percentage is missing, unreliable, or too optimistic under real load.

Current status: `0.1.0-beta.2`. The integration is HACS-compatible and ready for field validation, but public screenshots and broader live-system benchmarks are still being collected.

## What It Gives You

- `estimated_soc`: practical battery state of charge
- `time_to_empty`: estimated runtime while discharging
- `time_to_full`: estimated charge completion time
- `usable_soc`: SOC above a configured depletion-voltage cutoff
- `confidence`: current confidence in the forecast
- `prediction_health`: quick signal for whether the prediction is usable
- Diagnostic sensors for calibration, model spread, learned capacity, Peukert learning, and battery health

## Who This Is For

Use this if you have a lead-acid battery bank connected to Home Assistant and at least one useful voltage sensor.

Good fits:

- Home Assistant inverter monitoring
- Solar backup battery systems
- Tubular lead-acid battery banks
- Flooded, AGM, gel, and lead-carbon batteries
- UPS or off-grid systems where runtime matters more than a simple voltage display

This is not a BMS replacement. It estimates from Home Assistant telemetry and improves as it observes real charge and discharge behaviour.

## Inputs

Minimum:

- Battery voltage sensor
- Battery capacity in Ah
- Nominal voltage
- Battery type

Recommended:

- Battery current sensor, with charging and discharging direction
- Or separate charge power and discharge/load power sensors
- Battery temperature sensor
- Home Assistant Recorder enabled for the source sensors

The integration degrades gracefully when optional sensors are unavailable, but forecasts are stronger with current or power data.

## Supported Battery Types

- Flooded lead acid
- Tubular lead acid
- AGM
- Gel
- Lead carbon

See [docs/BATTERY_TYPES.md](docs/BATTERY_TYPES.md) for profile details.

## Installation

### HACS Custom Repository

1. In Home Assistant, open HACS.
2. Open Custom repositories.
3. Add this repository URL:

   ```text
   https://github.com/sundeepgoel72/HA-battery-remainingtime-integration
   ```

4. Select category `Integration`.
5. Install `Battery Remaining Time`.
6. Restart Home Assistant.
7. Go to Settings > Devices & services > Add integration.
8. Search for `Battery Remaining Time`.

### Manual Install

Copy `custom_components/battery_remaining_time` into your Home Assistant `custom_components` directory, restart Home Assistant, then add the integration from Devices & services.

## Quick Configuration

Start simple:

- Algorithm: `Ensemble`
- Battery type: your closest chemistry/profile
- Battery capacity: capacity from your battery bank label, in Ah
- Nominal voltage: `12`, `24`, `36`, `48`, `60`, or `72`
- Depletion voltage: leave default unless you know your safe cutoff
- Voltage sensor: required
- Current sensor: recommended
- History window: start with `60` minutes
- Update interval: start with `60` seconds

Example source sensors:

```text
sensor.inverter_battery_voltage
sensor.inverter_battery_current
sensor.inverter_charge_power
sensor.inverter_load_power
sensor.battery_temperature
```

See [QUICK_START.md](QUICK_START.md) for dashboard examples and troubleshooting.

## Example Dashboard Card

```yaml
type: entities
title: Battery Runtime
entities:
  - entity: sensor.battery_estimated_soc
  - entity: sensor.battery_time_to_empty
  - entity: sensor.battery_time_to_full
  - entity: sensor.battery_usable_soc
  - entity: sensor.battery_confidence
  - entity: sensor.battery_prediction_health
```

## How It Works

1. Home Assistant entities provide live battery telemetry.
2. Recorder history is analysed when available.
3. The integration detects whether the battery is resting, charging, discharging, floating, or under heavy discharge.
4. Multiple algorithms estimate SOC, TTE, and TTF.
5. Calibration evidence is collected from observed behaviour.
6. Confidence and prediction-health signals are exposed as Home Assistant sensors.

Supported algorithms include voltage OCV, coulomb counting, power flow, Peukert, hybrid, temperature-corrected, KiBaM, Shepherd, adaptive, and ensemble approaches.

See [docs/ALGORITHMS.md](docs/ALGORITHMS.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the technical model.

## Diagnostics

Primary diagnostics include:

- `prediction_health`
- `calibration_status`
- `algorithm_spread`
- `model_accuracy`
- `prediction_confidence`
- `active_algorithm`
- `usable_soc`
- `time_to_depletion`
- `configured_depletion_voltage`
- `learned_depletion_voltage`
- `depletion_voltage_confidence`
- `learned_peukert_exponent`
- `peukert_confidence`
- `peukert_observation_count`

Comparison sensors are exposed during beta field validation so model divergence is easy to see:

- `soc_ocv`, `soc_coulomb`, `soc_peukert`, `soc_hybrid`, `soc_ensemble`
- `tte_ocv`, `tte_coulomb`, `tte_peukert`, `tte_hybrid`, `tte_ensemble`
- `ttf_ocv`, `ttf_coulomb`, `ttf_peukert`, `ttf_hybrid`, `ttf_ensemble`

Home Assistant diagnostics download support is included for config-entry troubleshooting. It redacts configured entity IDs and the battery name before export.

## Field Validation

Before relying on automations that shut down equipment or switch loads, validate the forecast against your real battery for several cycles.

Recommended first checks:

1. Confirm `estimated_soc`, `time_to_empty`, `time_to_full`, `confidence`, and `prediction_health` are created.
2. Watch `algorithm_spread` during charge, idle, and discharge periods.
3. Compare the forecast against a known inverter display or manual runtime observation.
4. Let Home Assistant Recorder collect at least 24 hours of battery history.
5. Report mismatches with battery type, capacity, nominal voltage, source sensor names, and a diagnostics export.

## Documentation

- [QUICK_START.md](QUICK_START.md)
- [docs/SENSOR_REFERENCE.md](docs/SENSOR_REFERENCE.md)
- [docs/ALGORITHMS.md](docs/ALGORITHMS.md)
- [docs/BATTERY_TYPES.md](docs/BATTERY_TYPES.md)
- [docs/CALIBRATION.md](docs/CALIBRATION.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/RECORDER_BENCHMARKING.md](docs/RECORDER_BENCHMARKING.md)
- [docs/SCREENSHOTS.md](docs/SCREENSHOTS.md)

## Beta Readiness

Included:

- HACS-compatible metadata and config flow
- Stable config-entry identity
- Home Assistant Repairs issue for missing source sensors
- Home Assistant diagnostics download support with redaction
- Comparison sensors and spread/confidence diagnostics for field debugging
- Robust median ensemble aggregation
- Spread-based confidence grading
- SOC rate limiting and last-valid-SOC preservation

Still pending:

- UI screenshots captured from a live Home Assistant frontend
- Wider live-database Recorder benchmarking
- More field reports across battery types and inverter sensor sources

## Local Development

The local test surface is intentionally narrower than a full Home Assistant runtime.

Use the local environment for unit tests, import checks, and linting:

```bash
python -m pytest -q
```

Use a live Home Assistant instance for config-flow walkthroughs, entity verification, Recorder-backed behaviour, and end-to-end functional checks.

## Project Goal

Create a self-calibrating lead-acid battery prediction engine for Home Assistant that becomes more accurate through real-world battery observations.

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
