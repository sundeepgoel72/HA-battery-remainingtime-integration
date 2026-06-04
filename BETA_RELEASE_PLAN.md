# Beta Release Plan

## Target

- Release: `v0.1.0-beta.2`
- Positioning: community field-validation release
- Branch: `dev`
- Date: June 2, 2026

## Current Release Posture

The repository is ready for a HACS custom-repository beta from a code and validation standpoint. The remaining work is mostly release presentation and live-user confirmation rather than architectural or compatibility gaps.

Current live baseline:

- `prediction_health=ok`
- `confidence=high`
- `algorithm_spread=0.0`
- `source_evidence_status=live`
- `update_count=6923`
- `history_window_minutes=180`
- `capacity_confidence=low`
- `peukert_confidence=low`
- `peukert_observation_count=0`
- `effective_charge_efficiency=1.05`

Confirmed in the current codebase:

- `manifest.json` and `hacs.json` are aligned and HACS-compatible
- config flow and options flow are implemented
- recorder history, recorder fallback, diagnostics redaction, and Repairs behavior are implemented
- focused validation workflows and pytest coverage are present
- public docs now match the implemented algorithms and diagnostics surface

## Runtime Validation Matrix

| Check | Evidence | Status | Notes |
|---|---|---:|---|
| HACS install surface | `manifest.json`, `hacs.json`, `.github/workflows/hacs.yml`, `.github/workflows/validate.yml` | Pass | Metadata and HACS action are in place; live HACS UI install still depends on manual repo add in user environment. |
| Integration setup | `tests/test_integration_runtime.py` + live HA restart logs | Pass | Entry setup covered in tests and live HA initialized cleanly. |
| Integration reload | `tests/test_integration_runtime.py` | Pass | Update listener reload path is covered. |
| Integration unload | `tests/test_integration_runtime.py` | Pass | `async_unload_entry` removes coordinator state cleanly. |
| Home Assistant restart | Live HA smoke test on June 2, 2026 | Pass | Forecast resumed after restart without Battery Remaining Time traceback. |
| Integration removal | `tests/test_integration_runtime.py` unload path | Pass | Runtime removal semantics validated through unload behavior. |
| Options flow updates | `tests/test_config_flow.py` | Pass | Runtime options override and title sync are covered. |
| Missing sensors | `tests/test_integration_runtime.py` | Pass | Missing live and recorder evidence raises `UpdateFailed` and opens Repairs issue. |
| Recorder unavailable | `tests/test_history.py` | Pass | Recorder exception degrades to empty history without crashing. |
| Recorder fallback | `tests/test_integration_runtime.py` + live HA logs | Pass | Live startup used recorder fallback for voltage/current and forecasted successfully. |
| Diagnostics download | `tests/test_diagnostics.py` | Pass | Redaction of entity IDs and battery name is covered. |
| Repairs | `tests/test_integration_runtime.py` | Pass | Missing-source issue creation is covered. |
| No Battery Remaining Time startup tracebacks | Live HA logs | Pass | Unrelated HA integrations still log errors; Battery Remaining Time did not. |

## Benchmarks

- Synthetic baseline recorded in [docs/RECORDER_BENCHMARKING.md](./docs/RECORDER_BENCHMARKING.md)
- 7-day history windows are materially more expensive than 24-hour windows and should not be the default

## Screenshots

- See [docs/SCREENSHOTS.md](./docs/SCREENSHOTS.md)

## Remaining Beta Artifacts

1. Capture and commit the UI screenshots listed in `docs/SCREENSHOTS.md`
2. Confirm HACS custom-repository install end to end in the live HA frontend
3. Run the GitHub workflows after push and confirm green status
4. Characterize adaptive-learning convergence from live data and document any questionable learned values

## Release Decision

Release criteria are met for the integration itself:

- tests green
- diagnostics present
- Repairs behavior verified
- live Home Assistant restart and fallback behavior verified
- HACS and manifest validation automated
- stable live forecast baseline confirmed

The remaining open beta question is adaptive-learning convergence, not ensemble stability.

## Release Steps

1. Push the tested Phase 0 hardening commits on `dev`
2. Tag `v0.1.0-beta.2`
3. Push tag
4. Sync the tagged build into Home Assistant
5. Restart Home Assistant
6. Update handover with the exact release tag and runtime evidence
