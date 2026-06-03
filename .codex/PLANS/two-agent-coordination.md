# Two-Agent Coordination Plan

Use this repo with two roles sharing one checkout:

- Developer:
  implements changes, adds tests, updates task/status
- Debugger:
  isolates failures, validates runtime behavior, updates worklog/handover

Workflow:

1. Claim scope in `STATUS.md`.
2. Create or update a worklog entry for substantial work.
3. Record verification commands and outcomes before handoff.
4. Update `HANDOVER.md` with the exact next safe action.
