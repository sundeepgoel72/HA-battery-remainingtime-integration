# Battery Remaining Time - Algorithm Roadmap

## Implemented Architecture Targets

### Core Algorithms

1. Voltage OCV
2. Coulomb Counting
3. Peukert Runtime
4. Hybrid OCV + Coulomb
5. Temperature Compensated
6. KiBaM
7. Shepherd
8. Adaptive Hybrid

## User Configuration

### Battery Chemistry
- Flooded Lead Acid
- AGM
- Gel
- Custom

### Prediction Algorithm
- voltage_only
- current_flow
- power_flow
- hybrid_lead_acid
- adaptive_hybrid
- kibam
- shepherd

### History Window
- 15 minutes
- 30 minutes
- 60 minutes
- 6 hours
- 24 hours
- 7 days
- custom

## Learning Objectives

Adaptive engine learns:

- Actual usable capacity
- Peukert exponent
- Charge efficiency
- Temperature coefficient
- Prediction error statistics

## Ensemble Predictor (v1.0)

Combine multiple algorithms using confidence weighting.
