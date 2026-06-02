# Screenshots

## Purpose

This file tracks the release screenshots required for the HACS beta surface.

## Required Captures

| Screenshot | Purpose | Status | Notes |
|---|---|---:|---|
| HACS custom repository install | Show repo add and install flow | Planned | Capture after tagging `v0.1.0-beta.2` in the user HA environment |
| Config flow | Show first-run setup inputs | Planned | Use a representative 12 V tubular battery example |
| Device page | Show exposed entities and diagnostics | Planned | Include reduced entity surface and diagnostic grouping |
| Main dashboard | Show SOC, TTE, and TTF cards | Planned | Use a real battery with recorder-backed startup data |
| Diagnostics page | Show health/calibration diagnostics | Planned | Include `prediction_health`, `calibration_status`, and `algorithm_spread` |

## Capture Guidance

- Use the running Home Assistant instance after the beta tag is installed.
- Keep one screenshot per screen to avoid documentation churn.
- Prefer stable example entities so filenames do not need to change later.

## Suggested Filenames

- `docs/screenshots/hacs-install.png`
- `docs/screenshots/config-flow.png`
- `docs/screenshots/device-page.png`
- `docs/screenshots/dashboard.png`
- `docs/screenshots/diagnostics.png`
