# HACS Beta Release Summary

## Release Target

- Version: `v0.1.0-beta.2`
- Branch: `dev`
- Date: June 2, 2026
- Positioning: community field-validation beta

## Current Status

Estimated readiness: `90%`

The integration code, diagnostics, tests, and release automation remain in good shape, but a critical field defect was discovered in the ensemble path during idle conditions. The current build should be treated as a stabilization beta until the new spread/confidence and ensemble hardening are verified in live Home Assistant telemetry.

## What Is Implemented

- Config flow and options flow
- Stable unique IDs and a field-debug comparison sensor surface
- Recorder history integration with fallback behavior
- Repairs issue for missing source evidence
- Diagnostics download with redaction
- Adaptive learning for capacity, charge efficiency, model accuracy, and Peukert exponent
- Ensemble weighting with bounded adaptive weights
- Robust median ensemble aggregation and spread-based confidence
- SOC rate limiting and last-valid-SOC preservation
- Per-algorithm comparison sensors for SOC, TTE, and TTF
- Battery health, capacity retention, and profile optimization
- HACS metadata and validation workflows

## Validation Evidence

- `39 passed, 1 warning`
- `ruff check` passes
- `python -m compileall` passes
- live Home Assistant restart smoke test passed on the previous beta baseline
- current stabilization pass still needs a fresh HA smoke test after sync
- runtime setup/reload/unload/removal behavior covered in tests

## Runtime Validation Status

See [BETA_RELEASE_PLAN.md](./BETA_RELEASE_PLAN.md) for the full matrix.

Highlights from the previously validated beta baseline:

- setup: pass
- reload: pass
- unload/remove semantics: pass
- restart: pass
- missing sensors and Repairs issue: pass
- recorder unavailable fallback path: pass
- diagnostics download: pass

## Remaining Beta Artifacts

- live validation of the Issue #17 stabilization fix in Home Assistant
- UI screenshots listed in [docs/SCREENSHOTS.md](./docs/SCREENSHOTS.md)
- live recorder-database benchmarking follow-up beyond the synthetic baseline in [docs/RECORDER_BENCHMARKING.md](./docs/RECORDER_BENCHMARKING.md)

## Risk Summary

Main remaining risks are:

- rogue model behavior under idle / weak-source conditions still needs field confirmation
- field calibration quality over longer battery cycles
- recorder cost on very large databases with long windows
- real-user HACS onboarding feedback

## Release Recommendation

Keep `v0.1.0-beta.2` positioned as a field-validation beta. Do not advance the public beta claim until the ensemble-stability fix is synced into Home Assistant and validated against live telemetry.
