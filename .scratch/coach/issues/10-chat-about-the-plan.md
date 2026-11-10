# 10: Chat about the plan

**What to build:** The coach chat handles everything about the plan besides context: questions about the data and the coach's decisions, change requests weighed against the data and guardrails, counter-proposals by reply, the optional reason after a reject, and calibration changes (run discount, wrestling kcal, lifting kcal) through proposals.

**Blocked by:** 08 (Lift progression in the weekly decision), 09 (Proposals with approve and reject)

**Status:** ready-for-agent

- [x] Read tools for chat return aggregated data: weekly facts, daily facts, lift history, context notes, targets, training plan, proposals, coach profile; `load_skill` loads other skills by name
- [x] Questions ("why did you hold?", "how are my squats?") are answered from stored facts and verdicts, citing the rule in plain words
- [x] A change request ("can I go up 300?") is weighed against the data; if the user still wants it, a `user_request` proposal is created and the guardrails decide; a blocked request says which guardrail and when it could pass
- [x] A number in reply to an open proposal creates a `user_counter` proposal (the old one becomes superseded); if the coach would choose differently it says so once
- [x] A reason after a reject is stored on the proposal (and as a context note if it's about life or preferences)
- [x] Setup values given in chat are recorded; calibration values outside a phase start go through a `calibration_change` proposal
- [x] Tests with a scripted model cover a question answered from a stored verdict, a blocked request, a counter that supersedes a proposal, and a rejection reason

## Comments

- New read tools in `features/plan_chat.py`: `get_weekly_facts` (stored check-in: facts, verdict, rules, skip reason; default latest), `get_daily_facts` (`date` only, no `kind`: evening-kind facts plus that day's Hevy sessions judged by `progression.session`; the training kind is ticket 12's), `get_lift_history` (reads `progression._Judge` without changing progression.py, which ticket 12 owns), `load_skill`. TOOLS.md updated.
- Counters are code's: the counter tap is recorded (`migrations/10_counters.sql`, valid 24 h); a reply that is only a number, give or take filler words ("+50", "make it 80"), runs before the waist handler and becomes a `user_counter` proposal. A bare number keeps the proposal's sign; a one-value calibration proposal takes it as the new value. Anything else goes to the chat, which sees `counter_awaited`. "Says so once": when the counter differs from the coach's own proposal at the root of the counter chain and nobody in the chain said it yet, code adds `agent_disagrees` ("I'd have gone with +100 kcal a day on average: <reason>") to the new card. A blocked counter leaves the old proposal open and lists the guardrail details.
- Calibration approval recomputes the targets the way the phase start computed them: the expected counted activity moves by the new values' effect over the last 28 days; with `maintenance_includes_activity` (default) base maintenance moves the other way, so the average and the MFP goal stay and only day targets shift. Without it the average moves and the MFP goal is set once (`proposal:<id>` key). The new targets row has source `calibration` and is left out of `phases.target_history`, so it doesn't restart the lockout; `last_change.delta_kcal` in the weekly facts now comes from the surplus difference so calibration rows can't skew it.
