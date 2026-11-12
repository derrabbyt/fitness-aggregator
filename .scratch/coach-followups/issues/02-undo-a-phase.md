# 02: Undo (erase) a phase on explicit request

**What to build:** `request_phase_end` with mode `undo`, only when the user's message explicitly asks to erase or undo a phase (skill + tool description). The card lists what is deleted (the phase, its setup, targets, proposals, weekly verdicts and reports, day questions and confirmations from its days); Confirm deletes them in one transaction. MFP goal untouched. Works on the active phase and on the latest ended one.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Delete in one transaction; other phases untouched (test)
- [ ] Card lists the counts of what goes
- [ ] Tests green

Spec: `.scratch/coach-followups/spec.md`.
