# Algorithms

This document describes the prediction models supported by Battery Remaining Time.

## Voltage OCV

Uses open-circuit voltage as an SOC indicator.

Advantages:
- Simple
- Stable

Limitations:
- Requires resting conditions for best accuracy

## Coulomb Counting

Tracks charge entering and leaving the battery.

Advantages:
- Accurate short-term tracking

Limitations:
- Accumulates drift over time

## Power Flow

Uses charge and discharge power trends.

Advantages:
- Useful when current sensors are unavailable

Limitations:
- Requires efficiency assumptions

## Peukert

Models capacity reduction at higher discharge rates.

Advantages:
- Better lead-acid discharge prediction

Limitations:
- Battery specific

## Hybrid

Combines multiple estimation methods to improve stability.

## Temperature Corrected

Applies temperature compensation to battery estimates.

## KiBaM

Kinetic Battery Model using available and bound charge reservoirs.

## Shepherd

Dynamic battery model based on voltage behaviour.

## Adaptive

Learns battery characteristics from observed usage.

## Ensemble

Combines all available model outputs into a weighted prediction.