# 09: Proposals with approve and reject

**What to build:** When a verdict carries a proposal, code runs every guardrail and stores it as open or blocked. The weekly report shows an open proposal with approve, reject and counter buttons (counter replies are handled in ticket 10), or says plainly why no change is possible yet. Approve applies the change exactly once: targets update and the MFP goal is set to the new average daily target, once, read back, never retried.

**Blocked by:** 06 (MFP goal set on phase confirm), 07 (Weekly check-in: facts, verdict, report)

**Status:** ready-for-agent

- [ ] `propose_change` stores a proposal as `open` or `blocked_by_guardrail` with violations: max change (except a phase's first change), lockout, confirmation not met, rejected direction returning too early, unusable week, adherence gate, invalid calibration values
- [ ] An identical open proposal is referenced, not duplicated
- [ ] The report shows an open proposal with approve / reject / counter buttons; a blocked one shows no buttons and says when a change could come
- [ ] Approve uses one atomic claim: the change applies exactly once (surplus updated, targets recomputed, MFP goal set once and read back), the buttons are removed and the outcome shown; a second tap does nothing
- [ ] A failed MFP goal write is reported and not retried; the coach targets remain the approved ones
- [ ] Reject marks the proposal rejected and removes the buttons; the coach asks for an optional reason
- [ ] Unanswered proposals change nothing
- [ ] The next report lists changes applied that week (what, why, what to expect, when it's re-checked)
- [ ] Tests cover each guardrail, approve once with a double tap, a failed goal write, reject, and the next report listing the applied change
