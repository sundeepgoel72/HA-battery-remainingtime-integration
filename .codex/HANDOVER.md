# Battery Remaining Time - Current Handover

Updated: 2026-06-03

## Current State

The repo is in stabilization mode for field beta validation. The multi-agent coordination structure is now standardized under `.codex/` and `.agents/`.

Latest technical baseline from prior handover:

- branch: `dev`
- tag target: `v0.1.0-beta.2`
- local stabilization snapshot: `22e122f Harden ensemble stability and observability`
- validation result: `39 passed, 1 warning`

## What Was Completed Before This Handover

- Added adaptive Peukert learning, adaptive ensemble weighting, and runtime diagnostics.
- Hardened ensemble behavior against rogue outputs and synthetic `0%` idle collapse.
- Added comparison sensors and debug observability.
- Expanded validation workflows and beta release artifacts.

## What Still Matters Most

1. Confirm the new comparison and diagnostic entities behave correctly in a real Home Assistant instance.
2. Prove the ensemble stabilization fix holds under real telemetry over time.
3. Finish screenshots and HACS install validation for public beta readiness.

## Safe Resume Point

- Start from `.codex/TASK.md` and claim scope in `.codex/STATUS.md`.
- Use the archived detailed handover for deeper technical history:
  `.codex/HANDOVERS/2026-06-03-pre-reorg-handover.md`

## Risk Notes

- The main risk is false confidence from synthetic or insufficient source telemetry.
- Any change to predictor confidence, rate limiting, or calibration gating needs focused regression tests plus field verification.
