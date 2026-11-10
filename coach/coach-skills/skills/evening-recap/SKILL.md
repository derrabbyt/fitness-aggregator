---
name: evening-recap
description: Daily evening job. Decides whether today's intake vs target is worth a short note and writes it. Most days it sends nothing. Load with coach-core and the active phase skill. Input daily_facts (kind evening); output coach_message.schema.json.
---

# Evening recap

The missing-log reminder is a code rule and is not your job: code only calls you when
today's food, weight and steps are all logged. Questions about today's intake are code's
too: a suspected partial day (**That's all I ate** / **I'll log the rest**) or an
implausibly high one (**Real** / **Typo, I'll fix it in MFP**) gets a code question with
buttons instead of you, so when you are called today's kcal are either unremarkable or
confirmed by the user (`day.intake.confirmed`). Don't ask about them again.

## Decide whether to send

- **ER-SKIP** – `send: false` when today and the week so far are near target, or when the
  daily message limit (`messaging.max_unprompted_messages_per_day`, compared with
  `messages_sent_today`) is reached; put anything worth saying into `deferred_to_weekly`
  instead. Code enforces the limit too: a message past it is stored for the weekly report.
- **ER-SEND** – Send when one of these is true:
  - the week so far (`day.week_to_date.deviation_pct`, over the logged days) is outside
    `adherence.weekly_intake_tolerance_pct`, so the user can still steer the weekly total
  - protein or fat today is clearly off its target (`day.vs_target`; daily totals, never
    single meals)
  - `day.checks.implausible_intake` is true and the user confirmed it as real
    (`day.intake.confirmed`): only if the week so far is now off (above); no question
- Minor things (fiber, a slightly low protein day) go into `deferred_to_weekly`, one short
  sentence each with the numbers from the facts.
- In the glycogen window, don't comment on weight (code withholds it: `day.weight.withheld`).
- Today's target already includes its step kcal (`day.target_build_up`: base at the step
  goal + `step_kcal` + sessions + surplus; steps so far, run steps removed). A low or high
  target from steps is not a target miss; mention step kcal only when they explain the gap.
  Never tell the user to walk more (CORE-STEPS).

## Message

One to three short lines: today vs target, the week so far vs target, the one notable
thing. Facts only: no food suggestions, no tips (coach-core). If the week so far is off,
state the remaining weekly budget only if code gave it; never compute it. No buttons.
