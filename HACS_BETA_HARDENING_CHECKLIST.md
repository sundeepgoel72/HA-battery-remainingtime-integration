# HACS Beta Hardening Checklist

## Metadata

- [x] `manifest.json` contains `version`
- [x] `manifest.json` contains `iot_class`
- [x] `manifest.json` contains `homeassistant`
- [x] `manifest.json` contains `issue_tracker`
- [x] `hacs.json` uses `local_polling`

## Home Assistant Patterns

- [x] Config flow present
- [x] Options flow present
- [x] Stable config-entry unique ID
- [x] Config entry title stays aligned with editable battery name
- [x] Diagnostic entities marked as diagnostic
- [x] Repairs issue created for missing source evidence
- [x] Diagnostics download implemented with redaction

## Runtime Validation

- [x] Setup covered
- [x] Reload covered
- [x] Unload covered
- [x] Restart smoke tested
- [x] Missing sensor behavior covered
- [x] Recorder unavailable behavior covered
- [x] Recorder fallback covered
- [x] Diagnostics download covered

## Code Quality

- [x] `compileall` passes
- [x] `ruff` passes
- [x] `pytest` passes
- [x] Predictor, history, storage, config-flow, diagnostics, and runtime tests exist
- [x] HACS validation workflow present
- [x] General validation workflow present

## Documentation

- [x] `README.md` reflects the current entity surface and diagnostics
- [x] KiBaM and Shepherd documented as implemented
- [x] `BETA_RELEASE_PLAN.md` added
- [x] `docs/RECORDER_BENCHMARKING.md` added
- [x] `docs/SCREENSHOTS.md` added
- [ ] UI screenshots captured and committed
- [x] Recorder benchmark table populated with measured values

## Release Gate

- [x] Repo releasable on `dev`
- [x] Home Assistant integration smoke tested after sync
- [ ] Public beta release assets fully complete

## MVP 2 Beta Readiness

- [x] Stable forecast baseline confirmed in live Home Assistant telemetry
- [ ] UI screenshot set captured and committed
- [ ] HACS custom-repository install flow verified in the live frontend
- [ ] Adaptive-learning convergence characterized from live data
- [ ] Release notes and handover aligned with current live baseline
