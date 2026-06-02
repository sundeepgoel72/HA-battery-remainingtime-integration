# Battery Remaining Time - Handover

## Current State

The integration is on branch `dev`.

Recent work completed:

- Added HACS validation workflow at `.github/workflows/hacs.yml`.
- Updated README to match current supported battery types and roadmap.
- Wired configured depletion voltage into prediction inputs.
- Fixed battery type cycle-life lookup keys.
- Added config entry update listener so option changes reload the integration.
- Added recorder history timestamps and persisted `last_history_point_timestamp` so cumulative learning only processes new recorder intervals.
- Reworked model accuracy learning to use raw sensor evidence instead of scoring models against their own selected prediction.
- Marked learning, comparison, prediction health, calibration, and algorithm spread sensors as diagnostic entities.
- Trimmed normal forecast sensor attributes to reduce recorder payload.
- Added focused pytest coverage for config identity, runtime options, depletion voltage, cycle-life mapping, recorder timestamp filtering, and raw-anchor model scoring.
- Moved mutable options into `entry.options` and added a runtime config merge helper.
- Added Home Assistant Repairs issue creation for unavailable source sensor evidence.
- Removed the redundant `comparison.py` helper.
- Added adaptive Peukert exponent learning from recorder-backed discharge cycles ending at low-battery calibration anchors.
- Exposed `learned_peukert_exponent`, `peukert_confidence`, and `peukert_observation_count` as diagnostic statistics.
- Added focused pytest coverage for Peukert low-confidence fallback, medium-confidence learned exponent use, and diagnostic sensor registration.
- Completed Phase 3 adaptive learning by adding bounded adaptive ensemble weighting from learned model accuracy.
- Exposed `model_weighting`, `ensemble_weights`, and per-model `ensemble_weight` diagnostics.
- Reduced the Home Assistant entity surface so only the selected algorithm result is exposed as entities; alternate model outputs now live in diagnostics and coordinator logs.
- Completed the Phase 4 baseline by applying trusted learned capacity and charge efficiency to runtime predictions and exposing profile optimization / ageing diagnostics.
- Started Phase 5 hardening by adding Home Assistant diagnostics download support with redaction, syncing translations with the actual entity surface, and keeping config entry titles aligned when the battery name changes in options.
- Expanded Phase 0 validation into dedicated predictor, history, storage, config-flow, diagnostics, and runtime test files.
- Added `.github/workflows/validate.yml` for syntax checks, manifest validation, pytest, and hassfest.
- Added `BETA_RELEASE_PLAN.md` with a concrete runtime validation matrix.
- Added `docs/RECORDER_BENCHMARKING.md` with measured synthetic 60 min / 6 hr / 24 hr / 7 day history-window costs.
- Added `docs/SCREENSHOTS.md` to track required HACS/public-beta UI captures.
- Rewrote the HACS beta summary/checklist docs so they match the actual codebase and validation evidence.
- Updated roadmap and known issues to reflect implemented capacity, charge-efficiency, Peukert, model-accuracy, and adaptive ensemble learning.
- Hardened the ensemble path after a field defect where SOC collapsed to `0%` during idle conditions while confidence remained high.
- Replaced fragile ensemble mean behavior with robust median aggregation across valid model outputs.
- Switched confidence grading to spread-based thresholds with `very_low` support.
- Added SOC rate limiting and last-valid-SOC preservation so missing/untrusted source updates do not emit synthetic `0%`.
- Blocked calibration anchors when confidence is low, spread is high, or source evidence is recorder fallback / insufficient.
- Reintroduced per-algorithm comparison sensors for SOC, TTE, and TTF, and added `prediction_confidence` plus `active_algorithm` diagnostic aliases.
- Added per-update debug logging of per-algorithm SOC/TTE/TTF outputs plus spread/confidence.
- Added focused regression tests for spread-based confidence, robust ensemble behavior, comparison-sensor exposure, and calibration blocking under rogue-output conditions.

Validation performed:

- `python -m compileall custom_components/battery_remaining_time tests`
- `ruff check custom_components/battery_remaining_time tests`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
- Current result: `39 passed, 1 warning`
- The new stabilization pass has not yet been smoke-tested in live Home Assistant in this handover snapshot.

Latest release baseline:

- `phase4-baseline-2026-06-02`
- `e271a25 Advance Phase 5 beta hardening`
- `b1ed24b Expand Phase 0 validation suite`
- `ed9e8ad Prepare Phase 0 beta release artifacts`
- Release tag to use: `v0.1.0-beta.2`

Current local stabilization snapshot:

- Fixes Issue #17: ensemble collapse under rogue outputs
- Implements Issue #18: per-algorithm observability sensors
- Not yet committed in this snapshot

## Key Files

- `custom_components/battery_remaining_time/config_flow.py`
  Config flow, options flow, and stable config-entry unique ID generation.
- `custom_components/battery_remaining_time/coordinator.py`
  Reads source entities, fetches recorder history, builds prediction inputs, and updates persistent stats.
- `custom_components/battery_remaining_time/history.py`
  Recorder history fetching and conversion to `HistoryPoint` objects.
- `custom_components/battery_remaining_time/predictor.py`
  Core battery prediction algorithms and ensemble logic.
- `custom_components/battery_remaining_time/storage.py`
  Persistent learning state, calibration evidence, health, capacity, cycle, and model performance tracking.
- `custom_components/battery_remaining_time/sensor.py`
  Home Assistant sensor entities, diagnostic entities, device info, and entity registry identifiers.
- `custom_components/battery_remaining_time/events.py`
  Operating state and calibration-anchor detection.

## Remaining Work

Release-surface follow-up:

1. Sync the current stabilization pass into `/mnt/ssd/homeassistant/config/custom_components/battery_remaining_time`.
2. Restart Home Assistant and verify live forecast updates, comparison sensors, spread/confidence telemetry, and calibration blocking behavior.
3. Commit real frontend screenshots referenced in `docs/SCREENSHOTS.md`.
4. Confirm HACS custom-repository install flow end to end in the live user HA frontend.
5. Run the new GitHub validation workflows on GitHub after push and confirm green status.

Post-beta validation:

1. Identify which raw model path is producing the rogue idle SOC output in the field case.
2. Validate adaptive Peukert learning against real discharge cycles before treating learned exponent confidence as field-trusted.
3. Validate adaptive ensemble weights against field data before treating weighting confidence as final.
4. Validate Phase 4 ageing/profile optimization against longer field data before treating optimized capacity/efficiency as final.
5. Benchmark recorder cost against a real large recorder database, not only the current synthetic benchmark.
6. Confirm entity registry stability after real option edits and long-lived upgrades.

## Notes

The integration now compiles, passes `ruff`, and the local suite is at `39 passed, 1 warning`. The current priority is no longer feature expansion; it is proving that the new ensemble hardening actually prevents idle-SOC collapse in live Home Assistant telemetry. Public-beta readiness should be treated as temporarily reduced until that field validation is complete.
