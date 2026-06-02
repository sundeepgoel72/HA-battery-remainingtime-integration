# HACS Beta Release Summary

## Release Target

- Version: `v0.1.0-beta.2`
- Branch: `dev`
- Date: June 2, 2026
- Positioning: community field-validation beta

## Current Status

Estimated readiness: `97%`

The integration code, diagnostics, tests, and release automation are in good shape for a public beta. The remaining work is primarily UI screenshot capture and continued field validation rather than architectural or HACS-compatibility gaps.

## What Is Implemented

- Config flow and options flow
- Stable unique IDs and reduced default entity surface
- Recorder history integration with fallback behavior
- Repairs issue for missing source evidence
- Diagnostics download with redaction
- Adaptive learning for capacity, charge efficiency, model accuracy, and Peukert exponent
- Ensemble weighting with bounded adaptive weights
- Battery health, capacity retention, and profile optimization
- HACS metadata and validation workflows

## Validation Evidence

- `22 passed, 1 warning`
- `ruff check` passes
- `python -m compileall` passes
- live Home Assistant restart smoke test passes
- live recorder fallback behavior observed in HA logs
- runtime setup/reload/unload/removal behavior covered in tests

## Runtime Validation Status

See [BETA_RELEASE_PLAN.md](./BETA_RELEASE_PLAN.md) for the full matrix.

Highlights:

- setup: pass
- reload: pass
- unload/remove semantics: pass
- restart: pass
- missing sensors and Repairs issue: pass
- recorder unavailable fallback path: pass
- diagnostics download: pass

## Remaining Beta Artifacts

- UI screenshots listed in [docs/SCREENSHOTS.md](./docs/SCREENSHOTS.md)
- live recorder-database benchmarking follow-up beyond the synthetic baseline in [docs/RECORDER_BENCHMARKING.md](./docs/RECORDER_BENCHMARKING.md)

## Risk Summary

Main remaining risks are no longer code-structure risks. They are:

- field calibration quality over longer battery cycles
- recorder cost on very large databases with long windows
- real-user HACS onboarding feedback

## Release Recommendation

Proceed with `v0.1.0-beta.2` as a field-validation beta after pushing the tested baseline and syncing the release build into Home Assistant.
