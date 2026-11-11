# 01: Reset the coach (end or undo a phase, start over)

**What to build:** Not specced yet (user, 2026-11-11). The user wants to reset the coach later from Telegram or the web UI. For example: undo a test phase, end or abandon a phase, or start over with clean coach data, without someone stopping the service and restoring a database copy by hand.

**Blocked by:** None (to be specced first)

**Status:** needs-triage

## Notes for when this gets specced

- Today's manual way (2026-11-11, phase test): stop `coach`, copy `state/coach/coach.db` aside, start it; to undo, stop it, put the copy back, start it. Data synced in between comes back on the next sync. The MFP goal has to be set back separately: one `fitness_set_goal` write, read back once, never retried.
- Questions to settle: what a reset covers (only the phase and targets, or also proposals, verdicts, notes, profile, exercise classification, photos); whether it is undoable; whether it needs a confirm tap in Telegram (it changes targets and possibly the MFP goal, so probably yes, following the "nothing without a tap" rule); and what happens to the MFP goal.
