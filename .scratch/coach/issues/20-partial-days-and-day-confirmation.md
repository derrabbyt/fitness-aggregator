# 20: Partial days and confirming a day

**What to build:** Days logged only partly (e.g. 158 kcal) currently count as "logged" and drag the maintenance estimate and adherence down; only implausibly high days (> 2× target, ticket 11) are questioned. Add the low side, and let the user confirm a day as complete or real (user decision, 2026-11-10). The coach never writes to the MFP diary; confirmations live in the coach.

**Blocked by:** 17, 18 (same modules)

**Status:** ready-for-agent

- [x] Core param `data.partial_day_share: 0.5`: a day whose intake is below that share of the median of the user's other logged days in the 7 days around it (fall back to the daily target when fewer than 3 such days) is **incomplete** unless the user confirmed it. Schema, params, README assumption row; validator green
- [x] Incomplete days are excluded from the maintenance estimate (a week containing one is not usable), from weekly logging completeness and from adherence / intake vs target; daily and weekly facts mark them (`partial_suspected`, `confirmed`) and validate against the schemas
- [x] The evening job asks once per day about a suspected partial day, with buttons **That's all I ate** / **I'll log the rest**, and keeps the existing high-side question with **Real** / **Typo, I'll fix it in MFP**; days found after the evening (e.g. at the weekly check-in or a sync) are asked once in the next message that goes out. These questions count toward the daily message limit
- [x] **That's all I ate** and **Real** store a day confirmation (date, kind, the kcal it was confirmed at); the day then counts normally. If the day's synced kcal later change, the confirmation lapses and the day is checked again
- [x] Chat tool `confirm_day(date, kind: complete|real)` and the skills (coach-chat, evening-recap, weekly-report, TOOLS.md) cover "Tuesday was complete" / "yesterday's 4,000 was real"
- [x] Tests: a 158-kcal day excluded from maintenance and adherence, its question and both buttons, a chat confirmation, a confirmation lapsing after a later edit, the high-side "Real" confirmation, and a week usable again after confirmation

## Comments

- Logic in `fa_coach/daycheck.py` (statuses, confirm), questions/buttons/tool/syncer in
  `features/day_questions.py`, tables in `migrations/20_day_confirmations.sql`.
- Only unconfirmed suspected *partial* days are excluded; an unconfirmed implausibly high
  day is still counted (the ticket excludes only incomplete days). Its question now comes
  from code with buttons, no longer from the evening-recap model; on an evening whose day
  is in question the recap doesn't run (it would judge a number in question).
- Neighbours for the median are all other logged days within ±3 days (including other
  suspected days); the fallback target exists only inside the active phase, so a pre-phase
  day with < 3 logged neighbours is never suspected.
- Today is checked only at the evening job; the `day-checks` syncer looks at the last 7
  days of the active phase up to yesterday. Earlier and pre-phase days are excluded
  silently (confirmable in chat) and never asked about.
- "Next message that goes out" = the next unprompted message (`messaging.send`, incl. the
  exempt weekly check-in): pending questions follow it as their own cards via
  `messaging.after_send`, each counting toward the limit; one past the limit waits. Chat
  replies don't carry them.
- Asked once per (day, kind, kcal); "I'll log the rest" / "Typo" store nothing. A tap
  after the day's kcal changed confirms nothing ("I'll check it again").
- The phase-start "last diet intake" prefill (phases.py) still averages every logged day;
  out of scope here.
- intake_day gains required `partial_suspected` and `confirmed`; `logged: partial` (enum
  already had it) marks an unconfirmed suspected day, whose kcal stay visible.
