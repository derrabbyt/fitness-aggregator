---
name: weekly-report
description: Weekly job, step 2. Writes the weekly Telegram report from weekly_facts, the stored verdict and the propose_change result, including any change approved during the week and the items deferred from daily messages. Load with coach-core and the active phase skill. Output matches coach_message.schema.json.
---

# Weekly report

Input (assembled by code):

- `facts` – `weekly_facts` for the week
- `verdict` – the weekly-decision output
- `proposal_result` – the stored proposal returned by `propose_change` (status `open` or
  `blocked_by_guardrail` with violations), or null
- `changes_applied` – proposals approved since the last report
- `deferred` – observations held back from daily messages this week (`[{date, text}]`)
- `due` – waist and photo check-ins due in the coming week, `[{date, kind}]` with kind
  `waist` or `photos` (photos only while they're on); empty when nothing is due

Output: one JSON object matching `coach_message.schema.json` (`send: true`).

## Content, in this order (skip what's empty)

1. **Decision** – one or two sentences: the scenario in plain words and what happens. Never
   name the scenario letter alone; say what it means.
2. **Proposal** – if `proposal_result.status` is `open`: the change in kcal per day on
   average, why, and what to expect. Add buttons `approve_proposal`, `reject_proposal`,
   `counter_proposal` with `ref_id` = proposal id, and say a counter is "reply with your
   number". If `blocked_by_guardrail`: don't show buttons; say plainly that no change is
   possible yet and when it could be (from the verdict's reasoning).
3. **Weight** – 7-day average, weekly rate and the target band for this phase week; in the
   glycogen window say the jump is expected and not judged.
4. **Food** – weekly average vs target and whether the adherence gate passed. Macro, fiber
   or produce flags in one line each.
5. **Training** – how many counted lifts improved; PRs from the week; stalls and deload
   signals as flags only; sport-load note if applied. If `training.progression_met` is null,
   say in a few words that lift progression wasn't evaluated, and list the sessions only. For scenario D: "training needs a look",
   nothing more specific.
6. **Activity** – average steps only if relevant (step floor flag, unusual week).
7. **Changes applied this week** – for each: what changed, why, what to expect, when it gets
   re-checked (per the confirmation rules).
8. **Deferred items** – merged into the sections above if they fit, otherwise one short list.
9. **Next week** – what to expect (e.g. the band for next week, the jump after a carb
   increase) and anything due from `due`: waist, photos, with the day.
10. **Questions** – the verdict's `questions_for_user`, if any.

## Rules

- **WR-NUMBERS** – Only numbers from `facts`, `verdict` or `proposal_result`. No new
  calculations (CORE-NO-MATH).
- **WR-LENGTH** – Fits on one phone screen in a normal week; longer only when there's a
  proposal, an unusable week to explain, or several flags.
- **WR-UNUSABLE** – Unusable or adherence-gate week: say why in one sentence, what would
  make next week usable, and that the streak isn't lost.
- **WR-TONE** – Neutral and factual (coach-core). A missed target is information, not a
  failure.
