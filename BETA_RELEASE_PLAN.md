# HACS Beta Release Plan

**Review date:** 2026-06-02
**Target version:** 0.1.0-beta.2
**Branch reviewed:** dev

## Current release posture

The repository is close to a HACS custom-repository beta. Core integration structure is present and the public documentation is mostly aligned with the shipped code.

Confirmed in the current codebase:

- `manifest.json` declares domain, config flow, code owner, documentation, issue tracker, `version`, `iot_class`, and minimum Home Assistant version.
- `hacs.json` is present and uses `local_polling`.
- Config flow and options flow are implemented.
- Recorder history is used and guarded with fallback handling.
- Diagnostics export is implemented with redaction.
- Main, health, learning, and diagnostic sensors are present.
- Repairs issue text exists for unavailable source sensors.
- README, Quick Start, sensor reference, algorithm, battery-type, architecture, and calibration docs exist.

## Beta blockers

These should be completed before publishing a wider beta announcement:

1. **Runtime validation on a real Home Assistant instance**
   - Install through HACS custom repository.
   - Create a config entry.
   - Verify setup, reload, unload, restart, and removal.
   - Confirm no startup traceback.
   - Confirm Recorder fallback behaviour after source sensor startup delay.

2. **Automated validation workflow**
   - Add GitHub Actions for `hassfest` and basic Python/test validation.
   - Add at least smoke tests for config flow helpers, predictor models, history normalization, diagnostics redaction, and storage migration/load.

3. **Recorder cost benchmark**
   - Test 60 min, 6 h, 24 h, and 7 d history windows.
   - Record update duration and Recorder query cost.
   - Confirm default history window and docs are aligned.

4. **Screenshots and release assets**
   - Add config flow screenshot.
   - Add entities/device screenshot.
   - Add diagnostics screenshot.
   - Add sample dashboard screenshot or documented YAML.

5. **Release-note consistency**
   - Align beta release notes with current implementation.
   - Do not state KiBaM/Shepherd are missing if they remain implemented as selectable algorithms.
   - Make the beta limitation about field validation accuracy, not missing algorithm names unless verified.

## Recommended beta criteria

The beta can be tagged after the following minimum checklist is done:

- [ ] HACS custom repository install succeeds.
- [ ] Integration setup succeeds with voltage + current sensors.
- [ ] Integration setup succeeds with voltage + charge/discharge power fallback.
- [ ] Reload/unload/restart tested.
- [ ] Diagnostics download tested and reviewed for redaction.
- [ ] Repairs issue appears when source evidence is unavailable and clears when evidence returns.
- [ ] Recorder windows of 60 min and 24 h tested without visible performance regression.
- [ ] At least one real battery runtime session captured.
- [ ] Release notes updated for `0.1.0-beta.2`.
- [ ] Git tag and GitHub release created.

## Suggested issue map

### Milestone: HACS beta

- Validate HACS install and Home Assistant lifecycle.
- Add CI validation for HACS/HA compatibility.
- Benchmark Recorder history windows.
- Add screenshots and beta release assets.
- Clean up release notes and beta docs.

### Milestone: Post-beta field validation

- Calibrate confidence scoring from real logs.
- Add comparison sensors if diagnostic-only model outputs prove insufficient.
- Refine adaptive learning thresholds from observed batteries.
- Add multi-battery planning.

## Recommended release sequence

1. Finish beta blockers.
2. Run one local HA deployment test.
3. Tag `v0.1.0-beta.2`.
4. Create GitHub release using beta release notes.
5. Add repository to HACS as a custom repository for initial users.
6. Collect first-week feedback as GitHub issues.

## Decision

**Current status:** Beta candidate, not yet public-beta complete.

The code and documentation are strong enough for private/local beta testing now. Wider HACS beta should wait until runtime lifecycle validation, CI validation, Recorder benchmark notes, and screenshots are complete.
