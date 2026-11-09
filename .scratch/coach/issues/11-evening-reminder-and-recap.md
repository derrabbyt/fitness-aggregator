# 11: Evening reminder and recap

**What to build:** Each evening at the configured time, code sends one reminder if today's food, weight or steps are missing. If the day is logged, the evening-recap skill decides whether today is worth a short note (the week so far off target, protein or fat clearly off, or an implausible entry to ask about). Most evenings are silent; anything minor is deferred to the weekly report.

**Blocked by:** 05 (Phase start: reverse)

**Status:** ready-for-agent

- [ ] Daily facts (kind evening) are computed in code and validate against the daily-facts schema, including today vs daily target and the week so far vs target
- [ ] The missing-log reminder is code-only, at most once per day, and names what's missing
- [ ] The recap model returns a coach message; `send: false` produces no message and its deferred items are stored for the weekly report
- [ ] An implausible entry (e.g. a day far beyond any normal intake) produces a typo-or-real question
- [ ] The daily message limit (setup value) is respected
- [ ] No weight comments during the glycogen window
- [ ] Tests cover a missing-log reminder, a silent evening with a deferred item, an off-target week note, the message limit, and that the deferred item appears in the next weekly report
