# 10: Chat about the plan

**What to build:** The coach chat handles everything about the plan besides context: questions about the data and the coach's decisions, change requests weighed against the data and guardrails, counter-proposals by reply, the optional reason after a reject, and calibration changes (run discount, wrestling kcal, lifting kcal) through proposals.

**Blocked by:** 08 (Lift progression in the weekly decision), 09 (Proposals with approve and reject)

**Status:** ready-for-agent

- [ ] Read tools for chat return aggregated data: weekly facts, daily facts, lift history, context notes, targets, training plan, proposals, coach profile; `load_skill` loads other skills by name
- [ ] Questions ("why did you hold?", "how are my squats?") are answered from stored facts and verdicts, citing the rule in plain words
- [ ] A change request ("can I go up 300?") is weighed against the data; if the user still wants it, a `user_request` proposal is created and the guardrails decide; a blocked request says which guardrail and when it could pass
- [ ] A number in reply to an open proposal creates a `user_counter` proposal (the old one becomes superseded); if the coach would choose differently it says so once
- [ ] A reason after a reject is stored on the proposal (and as a context note if it's about life or preferences)
- [ ] Setup values given in chat are recorded; calibration values outside a phase start go through a `calibration_change` proposal
- [ ] Tests with a scripted model cover a question answered from a stored verdict, a blocked request, a counter that supersedes a proposal, and a rejection reason
