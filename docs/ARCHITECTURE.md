# Architecture

## High-Level Flow

Battery Sensors
→ Home Assistant Entities
→ Recorder History
→ Event Detection
→ Prediction Algorithms
→ Calibration Engine
→ Confidence Engine
→ Sensor Outputs

## Core Components

### History Engine

Uses Recorder history to derive trends and charging/discharging behaviour.

### Prediction Engine

Runs multiple battery prediction models.

### Calibration Engine

Collects evidence from observed battery behaviour.

### Confidence Engine

Calculates confidence based on:

- History quality
- Sensor availability
- Calibration readiness
- Model agreement

### Output Sensors

Provides:

- SOC
- TTE
- TTF
- Prediction Health
- Calibration Status

## Future Enhancements

- Algorithm comparison sensors
- Model divergence metrics
- Adaptive learning
- Capacity estimation