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
- Updated roadmap and known issues to reflect implemented capacity, charge-efficiency, Peukert, model-accuracy, and adaptive ensemble learning.

Validation performed:

- `python -m compileall custom_components/battery_remaining_time`
- `ruff check custom_components/battery_remaining_time`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest`

Latest pushed commit at handover time:

- `b992461 Refine battery learning and docs`

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

Highest priority:

1. Add Home Assistant integration tests for setup, reload, unload, and entity registry stability.
2. Add config-flow tests with Home Assistant test helpers for duplicate setup and options reload.
3. Add recorder integration tests against Home Assistant recorder fixtures.
4. Add manual runtime validation in a real Home Assistant instance.

Quality and architecture:

1. Consider moving verbose diagnostics into Home Assistant diagnostics support.
2. Review whether recorder history should preserve a full prediction context window while querying incremental learning windows separately.
3. Add richer repair guidance for partially degraded sources, such as missing current but available voltage.
4. Measure recorder query cost with long history windows and short update intervals.
5. Validate adaptive Peukert learning against real discharge cycles in Home Assistant before treating learned exponent confidence as beta-ready.
6. Validate adaptive ensemble weights against field data before treating weighting confidence as final.

Release checklist:

1. Run HACS validation workflow in GitHub Actions.
2. Test setup, reload, and unload inside a real Home Assistant instance.
3. Confirm entity registry stability after changing the integration name and options.
4. Confirm diagnostic entities appear as diagnostic in Home Assistant UI.
5. Exercise startup when source sensors are unavailable and later become available.
6. Verify recorder database load with long history windows.
7. Tag beta only after the Home Assistant integration smoke test passes.

## Notes

The integration now compiles, passes `ruff`, and has a focused unit test suite. Phase 3 adaptive learning is implemented. The most important remaining risk before beta is real Home Assistant runtime behavior, especially config-entry reloads, recorder query cost, Repairs issue display, adaptive-learning field calibration, and entity registry stability.
