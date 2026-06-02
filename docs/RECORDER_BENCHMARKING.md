# Recorder Benchmarking

## Scope

This benchmark measures recorder-history normalization and coordinator update cost for representative history windows:

- 60 minutes
- 6 hours
- 24 hours
- 7 days

The benchmark is synthetic but uses the real integration code paths for:

- recorder history normalization
- `HistoryPoint` construction
- predictor execution
- coordinator update flow

## Method

- sample cadence: 5 minutes
- signal set: voltage, current, charge power, discharge power, temperature
- runtime measured on the local development machine on June 2, 2026
- CPU and memory are process deltas from Python resource usage during each scenario

## Results

| Window | Samples per sensor | History build ms | Coordinator update ms | CPU ms | RSS delta MB | Warnings |
|---|---:|---:|---:|---:|---:|---|
| 60 min | 13 | 0.216 | 2.125 | 3.286 | 0.000 | none |
| 6 hr | 73 | 2.878 | 1.796 | 5.181 | 0.125 | none |
| 24 hr | 289 | 38.196 | 2.284 | 40.940 | 0.125 | none |
| 7 day | 2017 | 1769.864 | 6.377 | 1773.377 | 0.500 | none |

## Interpretation

- 60 minutes and 6 hours are expected to be negligible on normal hardware.
- 24 hours should remain comfortable for default polling intervals.
- 7 days is the stress window. The predictor itself remains fast, but history normalization dominates the cost and should be treated as an advanced diagnostic setting rather than a default.

## Operational Guidance

- default recommendation remains 60 minutes
- 24 hours is reasonable for deeper adaptive learning and startup recovery
- 7 days should be treated as a benchmarking/diagnostic mode until more field data is gathered

## Follow-Up

- rerun these measurements against a live Home Assistant recorder database with real state volume
- add coordinator timing logs if real-world 7-day queries become a bottleneck
