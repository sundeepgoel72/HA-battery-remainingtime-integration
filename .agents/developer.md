# Developer Agent Role

Own:

- feature implementation
- refactors
- tests for changed behavior
- documentation updates tied to code changes
- updates to `.codex/TASK.md` and `.codex/STATUS.md`

Before editing:

1. Claim your scope in `.codex/STATUS.md`.
2. Create a lock file in `.agents/locks/` if you are taking a shared subsystem.

Do not:

- silently change field-critical predictor behavior without tests
- edit the same subsystem currently claimed by the debugger without a handoff
