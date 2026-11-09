# 11: Evening reminder and recap

**What to build:** Each evening at the configured time, code sends one reminder if today's food, weight or steps are missing. If the day is logged, the evening-recap skill decides whether today is worth a short note (the week so far off target, protein or fat clearly off, or an implausible entry to ask about). Most evenings are silent; anything minor is deferred to the weekly report.

**Blocked by:** 05 (Phase start: reverse)

**Status:** ready-for-agent

- [x] Daily facts (kind evening) are computed in code and validate against the daily-facts schema, including today vs daily target and the week so far vs target
- [x] The missing-log reminder is code-only, at most once per day, and names what's missing
- [x] The recap model returns a coach message; `send: false` produces no message and its deferred items are stored for the weekly report
- [x] An implausible entry (e.g. a day far beyond any normal intake) produces a typo-or-real question
- [x] The daily message limit (setup value) is respected
- [x] No weight comments during the glycogen window
- [ ] Tests cover a missing-log reminder, a silent evening with a deferred item, an off-target week note, the message limit, and that the deferred item appears in the next weekly report

## Comments

- Tests cover the reminder, a silent evening with a deferred item, an off-target week note and the
  message limit, plus that deferred items are stored and readable by week
  (`messaging.deferred(coach, week_start, week_end)`). The last box stays open until the weekly
  report (ticket 07) reads them.
- The daily message limit and deferred items live in `fa_coach/messaging.py` (tables in
  `migrations/11_messaging.sql`): `messaging.send(coach, text, now, kind=..., exempt=False)` counts
  and enforces the limit (`exempt=True` for the reset question), `sent_today`, `can_send`, `limit`;
  `defer(coach, day, text, source, now)` / `deferred(coach, start, end)`.
- The evening job syncs before deciding (the scheduler syncs only every 4 h), and runs before the
  stale-data job so that sync counts there. It runs once per day from the reminder time; a day
  whose reminder went out gets no recap later that evening.
- "Logged" = any food entry in MFP (as in `history.days`); MFP can't tell a partial day, so
  `intake.logged` is `complete` or `missing`. Missing steps = none or 0.
- Week so far = the phase week to today, over the days with food logged (`days_logged` added).
- Schema additions to daily facts: `day.vs_target` (kcal/protein/fat % of target), `day.checks.implausible_intake`,
  `day.weight.withheld` (in the glycogen window code withholds weight values), `week_to_date.days_logged`.
  New core param `data.implausible_intake_factor: 2` (assumption, listed in the skills README).
- A recap the model wants to send past the limit is stored as a deferred item. Recap buttons are ignored.

