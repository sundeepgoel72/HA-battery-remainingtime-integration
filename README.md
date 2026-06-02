# Battery Remaining Time for Home Assistant

Battery Remaining Time is a Home Assistant custom integration that estimates battery State of Charge (SOC), Time To Empty (TTE), and Time To Full (TTF) for lead-acid battery systems using Home Assistant Recorder history.

The project is designed as a self-calibrating battery prediction engine that improves accuracy over time by collecting evidence from real-world battery behaviour.

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
2. Recorder history is analysed over a configurable history window.
3. Battery operating state is detected.
4. Multiple prediction algorithms estimate SOC, TTE and TTF.
5. Calibration evidence is collected from observed battery behaviour.
6. Confidence scores are generated.
7. The selected algorithm result is exposed as Home Assistant entities, while alternate model outputs remain in diagnostics and logs.

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
- Prediction diagnostics
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
- learned_peukert_exponent
- peukert_confidence
- peukert_observation_count

Diagnostics expose confidence, algorithm selection, event state, calibration readiness, history window and calibration evidence.

The integration does not expose per-model SOC entities by default. Non-selected model outputs, spread, and ensemble weighting remain available through diagnostic attributes and coordinator logs.

## Architecture

Sensors → Recorder History → Event Detection → Prediction Models → Calibration Engine → Confidence Engine → Home Assistant Entities

For a detailed description see docs/ARCHITECTURE.md.

## Documentation

- docs/ALGORITHMS.md
- docs/BATTERY_TYPES.md
- docs/CALIBRATION.md
- docs/ARCHITECTURE.md
- docs/adaptive-peukert-learning.md

## Installation

Add the repository to HACS as a custom repository:

https://github.com/sundeepgoel72/HA-battery-remainingtime-integration

## Roadmap

Phase 1

- Field validation
- Accuracy testing

Phase 2

- Comparison sensors
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
