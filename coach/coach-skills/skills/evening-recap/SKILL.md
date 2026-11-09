---
name: evening-recap
description: Daily evening job. Decides whether today's intake vs target is worth a short note and writes it. Most days it sends nothing. Load with coach-core and the active phase skill. Input daily_facts (kind evening); output coach_message.schema.json.
---

# Evening recap

The missing-log reminder is a code rule and is not your job. You only look at a day that
is logged.

## Decide whether to send

- **ER-SKIP** – `send: false` when the day is missing or partial (the reminder handles it),
  when today and the week so far are near target, or when the daily message limit
  (`messaging.max_unprompted_messages_per_day`) is reached; put anything worth saying into
  `deferred_to_weekly` instead.
- **ER-SEND** – Send when one of these is true:
  - the week so far (`day.week_to_date.deviation_pct`) is outside
    `adherence.weekly_intake_tolerance_pct`, so the user can still steer the weekly total
  - protein or fat today is clearly off its target (daily totals; never single meals)
  - an implausible entry today (e.g. a day far beyond any normal intake) – ask if it's a
    typo or real (`odd_log`)
- In the glycogen window, don't comment on weight.

## Message

One to three short lines: today vs target, the week so far vs target, the one notable
thing. Facts only: no food suggestions, no tips (coach-core). If the week so far is off,
state the remaining weekly budget only if code gave it; never compute it.
