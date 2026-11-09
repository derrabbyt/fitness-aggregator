# 06: MFP goal set on phase confirm

**What to build:** Confirming a phase sets the user's MFP goal to the new average daily target and macros. The api gets a write tool for this that only coach code calls: once, read back once, never retried. The food bot and the coach model never see it.

**Blocked by:** 05 (Phase start: reverse)

**Status:** ready-for-agent

- [ ] The api's tools endpoint has `fitness_set_goal` (calories, protein, carbs, fat) that sets the MFP nutrition goal and returns the stored goal
- [ ] `fitness_set_goal` is not in the food bot's read-tool allowlist and is never offered to the coach model
- [ ] On phase confirm, coach code calls it once, then reads the goal back and reports in the confirmation message whether MFP now shows the new goal
- [ ] A failed or uncertain write is reported to the user and not retried; the phase stays active and the coach targets stay as confirmed
- [ ] Checked once by hand against live MFP (noted in the ticket's comments)
- [ ] Tests with the fake api client cover a successful write, a failed write that isn't retried, and that a second confirm tap doesn't write again
