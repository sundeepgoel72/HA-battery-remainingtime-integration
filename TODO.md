# Battery Remaining Time - TODO

## Task 2 - Adaptive Peukert Estimation

Implement adaptive Peukert exponent learning from real discharge evidence.

Completed:

- Learn from recorder discharge windows that end at low-battery calibration anchors.
- Compare observed runtime against Peukert-adjusted predicted runtime.
- Persist `learned_peukert_exponent`, `peukert_confidence`, and `peukert_observation_count`.
- Fall back to the default exponent while confidence is low.
- Feed the learned exponent into existing Peukert-capable algorithms once confidence reaches medium.
- Expose learned Peukert statistics as diagnostic sensors.
- Add focused pytest coverage for fallback and trusted learned exponent behavior.

Status: In progress pending real Home Assistant discharge-cycle validation.

## Task 3 - Usable SOC / Depletion Voltage Completion

Complete depletion-voltage feature.

Add:

- `sensor.usable_soc`
- `sensor.time_to_depletion`

Add diagnostics:

- `configured_depletion_voltage`
- `learned_depletion_voltage`

Add event state:

- `depletion_imminent`

Preserve existing `estimated_soc` behaviour.

Status: Pending.

## Task 4 - Adaptive Ensemble Weighting

Replace static ensemble weighting with adaptive weighting.

Requirements:

- Use `model_accuracy` statistics.
- Weight more accurate models higher.
- Prevent runaway weighting.
- Keep all models active.

Expose:

- `model_weighting`
- `ensemble_weights`

Update diagnostics.

This moves the project toward a genuine self-learning predictor.

Completed:

- Uses learned `model_accuracy` statistics at forecast time.
- Weights more accurate models higher.
- Keeps every model with a valid SOC estimate active.
- Caps normalized model weights to prevent runaway dominance.
- Exposes `model_weighting` and `ensemble_weights` in diagnostic attributes.
- Adds per-model `ensemble_weight` attributes on model SOC sensors.
- Adds focused pytest coverage for weighting behaviour and diagnostics metadata.

Status: Complete pending field validation.

## Task 5 - HACS Beta Hardening

Prepare for public HACS beta.

Review:

- `manifest.json`
- diagnostics
- translations
- entity names
- unique IDs
- config flow
- options flow

Produce:

- README improvements
- screenshots required
- beta release checklist

Implement any low-risk fixes.

Progress:

- Added Home Assistant diagnostics download support with config redaction.
- Synced translation coverage with the current entity/config-flow surface.
- Added config-entry title sync when the battery name changes in options.
- Added `issue_tracker` metadata and bumped beta version to `0.1.0-beta.2`.
- Synced README, beta checklist, release summary, and handover notes.
- Added a validation workflow with compile, manifest validation, pytest, and hassfest.
- Added a Phase 0 runtime validation plan and synthetic recorder benchmark results.

Status: In progress. Remaining item is committing UI screenshots from the live Home Assistant frontend.

## Task 6 - Test Suite

Create pytest coverage for:

- SOC algorithms
- ensemble engine
- calibration engine
- adaptive learning
- health calculations
- depletion voltage

Target:

- >= 80% coverage

Status: Pending.

Progress:

- Added adaptive Peukert learning unit coverage for low-confidence fallback and medium-confidence learned exponent use.
- Added diagnostic sensor key coverage for Peukert learning statistics.
- Added adaptive ensemble weighting unit coverage.
- Split tests into predictor, history, storage, config-flow, diagnostics, and integration runtime coverage.

## Task 7 - Ensemble Stability and Observability

Stabilize the ensemble path for field beta and expose enough telemetry to diagnose rogue models immediately.

Requirements:

- Add per-algorithm debug logging for SOC, TTE, and TTF.
- Replace fragile ensemble mean behavior with robust aggregation.
- Drive confidence from algorithm spread.
- Add SOC rate limiting for impossible transitions.
- Preserve last valid SOC when source telemetry becomes unavailable.
- Block calibration evidence generation when prediction trust is low.
- Expose comparison sensors and diagnostic aliases for field debugging.

Completed:

- Added robust median ensemble aggregation across valid SOC values.
- Rejects invalid SOC values outside `0-100%`.
- Uses spread-based confidence thresholds with `very_low` support.
- Rate-limits impossible SOC transitions and downgrades trust when limiting is applied.
- Preserves the last valid SOC instead of emitting synthetic `0%` on bad updates.
- Blocks calibration anchors when confidence is low, spread is too high, or source evidence is fallback/insufficient.
- Exposes `soc_*`, `tte_*`, and `ttf_*` comparison sensors for OCV, Coulomb, Peukert, Hybrid, and Ensemble.
- Exposes `prediction_confidence` and `active_algorithm` diagnostic aliases.
- Adds focused pytest regression coverage for spread confidence, robust ensemble behavior, and calibration blocking.

Status: Pushed and deployed. Pending longer field validation and HA UI confirmation of the new comparison-sensor surface.
