# Battery Remaining Time for Home Assistant

Battery Remaining Time is a Home Assistant custom integration focused on lead-acid battery systems.

It estimates state of charge (SOC), time to empty (TTE), time to full (TTF), battery operating state, prediction confidence and calibration status.

## Features

- Config Flow support
- Recorder history integration
- Multiple battery estimation algorithms
- Calibration evidence collection
- Persistent statistics
- Prediction diagnostics
- Local-only operation
- HACS compatible

## Supported Battery Types

Current focus:

- Flooded Lead Acid
- Tubular Lead Acid

Planned:

- AGM
- Gel
- Lead Carbon

## Diagnostics

Diagnostic entities include prediction_health and calibration_status.

## Installation

Add this repository as a custom HACS integration repository:

https://github.com/sundeepgoel72/HA-battery-remainingtime-integration

## Roadmap

- Algorithm comparison sensors
- Model divergence metrics
- Adaptive learning
- Self-calibration improvements

## Project Goal

Create a self-calibrating lead-acid battery prediction engine for Home Assistant using Recorder history and observed battery behaviour.
