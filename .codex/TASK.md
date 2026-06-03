# Battery Remaining Time - Current Task

## Goal

Stabilize the integration for field beta use and make debugging handoff-safe across Codex sessions.

## Active Priorities

1. Verify the new comparison sensors and diagnostic aliases in the Home Assistant UI and entity registry.
2. Capture and commit the live UI screenshots tracked in `docs/SCREENSHOTS.md`.
3. Confirm the HACS custom-repository install flow end to end.
4. Validate that ensemble hardening prevents idle-SOC collapse in real telemetry.

## Acceptance Criteria

- Live field validation confirms no synthetic idle collapse to `0%` under missing or rogue inputs.
- Comparison and diagnostic sensors are visible and interpretable in Home Assistant.
- Public-beta artifacts and screenshots are complete.
- Handover, status, and worklog records are sufficient for either agent to resume work without prior chat context.

## Out of Scope

- New major prediction models
- Broad architecture changes
- Removal of existing adaptive-learning observability
