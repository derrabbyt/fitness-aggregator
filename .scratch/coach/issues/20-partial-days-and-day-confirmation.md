# 20: Partial days and confirming a day

**What to build:** Days logged only partly (e.g. 158 kcal) currently count as "logged" and drag the maintenance estimate and adherence down; only implausibly high days (> 2× target, ticket 11) are questioned. Add the low side, and let the user confirm a day as complete or real (user decision, 2026-11-10). The coach never writes to the MFP diary; confirmations live in the coach.

**Blocked by:** 17, 18 (same modules)

**Status:** ready-for-agent

- [ ] Core param `data.partial_day_share: 0.5`: a day whose intake is below that share of the median of the user's other logged days in the 7 days around it (fall back to the daily target when fewer than 3 such days) is **incomplete** unless the user confirmed it. Schema, params, README assumption row; validator green
- [ ] Incomplete days are excluded from the maintenance estimate (a week containing one is not usable), from weekly logging completeness and from adherence / intake vs target; daily and weekly facts mark them (`partial_suspected`, `confirmed`) and validate against the schemas
- [ ] The evening job asks once per day about a suspected partial day, with buttons **That's all I ate** / **I'll log the rest**, and keeps the existing high-side question with **Real** / **Typo, I'll fix it in MFP**; days found after the evening (e.g. at the weekly check-in or a sync) are asked once in the next message that goes out. These questions count toward the daily message limit
- [ ] **That's all I ate** and **Real** store a day confirmation (date, kind, the kcal it was confirmed at); the day then counts normally. If the day's synced kcal later change, the confirmation lapses and the day is checked again
- [ ] Chat tool `confirm_day(date, kind: complete|real)` and the skills (coach-chat, evening-recap, weekly-report, TOOLS.md) cover "Tuesday was complete" / "yesterday's 4,000 was real"
- [ ] Tests: a 158-kcal day excluded from maintenance and adherence, its question and both buttons, a chat confirmation, a confirmation lapsing after a later edit, the high-side "Real" confirmation, and a week usable again after confirmation
