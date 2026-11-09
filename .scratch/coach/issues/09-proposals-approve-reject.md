# 09: Proposals with approve and reject

**What to build:** When a verdict carries a proposal, code runs every guardrail and stores it as open or blocked. The weekly report shows an open proposal with approve, reject and counter buttons (counter replies are handled in ticket 10), or says plainly why no change is possible yet. Approve applies the change exactly once: targets update and the MFP goal is set to the new average daily target, once, read back, never retried.

**Blocked by:** 06 (MFP goal set on phase confirm), 07 (Weekly check-in: facts, verdict, report)

**Status:** ready-for-agent

- [x] `propose_change` stores a proposal as `open` or `blocked_by_guardrail` with violations: max change (except a phase's first change), lockout, confirmation not met, rejected direction returning too early, unusable week, adherence gate, invalid calibration values
- [x] An identical open proposal is referenced, not duplicated
- [x] The report shows an open proposal with approve / reject / counter buttons; a blocked one shows no buttons and says when a change could come
- [x] Approve uses one atomic claim: the change applies exactly once (surplus updated, targets recomputed, MFP goal set once and read back), the buttons are removed and the outcome shown; a second tap does nothing
- [x] A failed MFP goal write is reported and not retried; the coach targets remain the approved ones
- [x] Reject marks the proposal rejected and removes the buttons; the coach asks for an optional reason
- [x] Unanswered proposals change nothing
- [x] The next report lists changes applied that week (what, why, what to expect, when it's re-checked)
- [x] Tests cover each guardrail, approve once with a double tap, a failed goal write, reject, and the next report listing the applied change

## Comments

- Code lives in `fa_coach/proposals.py` (logic) and `features/proposals.py` (hooks, buttons,
  tools); tables in `migrations/09_proposals.sql` (`proposals`, `proposal_cards`).
- `weekly_checkin.py` got one small hook, `report_finish_hooks`: code (not the report model)
  decides the proposal buttons, and adds the proposal / blocked / applied lines when the
  report falls back to code's text.
- Registered model tools `propose_change`, `get_proposals`, `add_rejection_reason` (ticket 10
  uses them, it shouldn't register them again). An open `user_request` / `user_counter`
  proposal from the tool gets its own card (`proposal:<id>`) with the three buttons, sent
  during the tool call, so it lands before the model's reply. A `proposals` state provider
  tells the chat model about open proposals and a rejection waiting for its reason (24 h).
- Counter tap: asks for the number and leaves the proposal open with its buttons (nothing
  was decided, so the spec's "buttons removed after any tap" isn't applied to it).
- Approving a calorie change supersedes the phase's other open calorie proposals (they were
  based on the old targets); their cards say so. Not in the spec; prevents stacking two
  changes from stale cards.
- New targets row: valid from the approval day; macros at the current macro reference weight.
- Calibration approve updates the phase's setup value only (counted from today); targets
  rows and the MFP goal are not recomputed. Ticket 10 may want more.
- Guardrail detail texts are code's (`guardrail.details` added to proposal.schema.json, with
  `earliest_checkin`). The "too fast" scenario per phase (reverse_bulk E, cut too_fast) is
  a constant in code, not a param. Lockout counts usable weeks starting on or after the last
  change's day; rejected-return counts the streak in that direction from the rejection day.
  A user_request's week defaults to the latest stored check-in.
- proposal.schema.json `new_values`: added `lifting_kcal_per_session`; ranges moved to the
  guardrail (phase_setup ranges) so a blocked proposal can hold out-of-range values.
