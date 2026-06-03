# Battery Remaining Time - Codex Project Context

## Objective

Develop and stabilize the Home Assistant `battery_remaining_time` custom integration for public beta use through HACS.

Primary goals:

- Produce reliable battery remaining time estimates
- Keep adaptive learning bounded and observable
- Make debugging safe in live Home Assistant deployments
- Preserve a clear validation and release trail

## Project Shape

Core integration code lives in:

- `custom_components/battery_remaining_time/`
- `tests/`
- `.github/workflows/`
- `docs/`

Primary behavior areas:

- config flow and options flow
- recorder-backed history ingestion
- runtime coordinator and event detection
- prediction algorithms and ensemble behavior
- persistent adaptive learning state
- diagnostic and comparison sensors

## Current Working Model

This repo is organized for two Codex agents sharing the same checkout:

- Developer agent:
  feature implementation, refactors, tests, docs updates
- Debugger agent:
  reproduction, runtime validation, regression isolation, field-issue analysis

Canonical coordination files live in `.codex/`.

## Local Test Model

The local `.venv` is intentionally narrow.

* Use it for unit tests, import checks, linting, and helper-level verification.
* Do not try to mirror a full Home Assistant runtime in the venv.
* Validate config flow, entity lifecycle, Recorder-backed behaviour, and other functional scenarios in the live Home Assistant instance.

## Durable Constraints

- Do not remove existing Home Assistant entity IDs or unique ID stability without explicit migration handling.
- Prefer focused pytest coverage for every behavior change in predictor, coordinator, storage, or config flow paths.
- Treat field stability as more important than feature expansion.
- Keep runtime diagnostics available for debugging adaptive behavior.

## Current Baseline

- Branch in use per handover: `dev`
- Latest validated beta tag in handover: `v0.1.0-beta.2`
- Current focus is stabilization and field validation, not major feature expansion

## Important Commands

Validation commands recorded in handover:

```bash
python -m compileall custom_components/battery_remaining_time tests
ruff check custom_components/battery_remaining_time tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

## Coordination Rules

- Update `.codex/TASK.md` when the active goal or acceptance criteria changes.
- Update `.codex/STATUS.md` at session start, before risky edits, after validation, and at session end.
- Update `.codex/HANDOVER.md` when work transfers between agents or sessions.
- Archive significant transfer notes in `.codex/HANDOVERS/`.
