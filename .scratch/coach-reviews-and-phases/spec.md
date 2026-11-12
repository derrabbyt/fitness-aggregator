# Coach: block review, phase review with photos, cut and maintenance

Status: ready-for-agent

Sources: the questions of 2026-11-12, `SPEC.md` (Scheduled cadence, Reports, Reverse and bulk settings, Photos and measurements, Other phases), `docs/reference/training-principles/02-fat-loss-coaching-protocol.txt` (deficit levels, target met / stalled, cut macros), `.scratch/coach/spec.md` (Out of Scope), `GLOSSARY.md`.

## Problem Statement

The coach runs one phase type, the reverse into a bulk.
- **No step back:** the block and phase reviews from `SPEC.md` don't exist, so nothing looks back over a training block or a whole phase.
- **Photos unused:** photos and waist are collected but never looked at, so the body-fat advice near 23–24 % can't happen.
- **No cut:** the cut and maintenance phases are drafts that phase start refuses, so the coach can't take me into the cut or mini-cut I'll need after the bulk.

## Solution

- **Block review:** every training block, a fixed number of weeks from the phase start (setup value `block_weeks`, default 5). I can also say "block done" to end one early.
  - **Content:** lift trends, stalls, fatigue and deload signals, a session-volume note, and what's next.
  - **Advice:** evidence-based food for thought in words, a deload week included when the signals point there. It never becomes a proposal, and I can talk about it in chat.
- **Phase review:** every 10 weeks during a phase and always when one ends.
  - **Content:** progress against the plan (weight against the band and the time goal, the strength trend), the maintenance estimate, the waist trend, a photo comparison, a goal check, and what comes next.
  - **Calibration:** when the run discount or the wrestling kcal have drifted, it proposes new values as calibration proposals I approve with a tap, as `SPEC.md` says.
  - **After a phase ends:** the coach asks what comes next.
- **Photo review:** at every photo check-in (every 2 weeks, photos on), the model estimates body fat from the photos.
  - **Comparison:** only like for like, at similar leanness.
  - **My own estimate:** always wins when I give one.
  - **Mini-cut advice:** as the estimate nears ~23–24 % in a bulk, the coach advises a mini-cut or ending the bulk. This is advice, never a stop.
- **Cut:** phase start accepts `cut`. I pick a level or give a goal.
  - **Levels:**
    - **Conservative:** −500 kcal a day, about −0.47 kg a week.
    - **Moderate:** −750, about −0.7, the default.
    - **Aggressive:** −1,000, about −0.93. The coach warns that it's for experienced dieters.
  - **Goal instead:** I give a goal weight (or body fat) and a date. The coach derives the rate and deficit it needs, caps it at −1,000 with the warning past moderate, and suggests the level.
  - **Start and target:** start kcal = the maintenance estimate − the deficit, shown in the preview for me to confirm or change. The target rate = deficit × 7 / 7,500 kg a week.
  - **Mini-cut:** a cut with an end date I set.
  - **Weekly band:** the target rate ±40 %. Slower than the band counts as stalled: with full adherence, 100–200 kcal less a day (carbs first) or +1–2k steps. Without adherence, no change until a clean week. Faster than the band: 100 kcal more, to protect muscle.
  - **Macros:** protein 2.5 g/kg, fat 0.6 g/kg (floor), carbs the rest.
  - **Strength:** holding lifts counts as success; several lifts dropping flags the deficit or recovery.
- **Maintenance** (kept small): phase start accepts `maintenance` with start kcal = the maintenance estimate. Flat is within ±0.1 kg a week; a drift beyond ±0.2 kg a week for 2 weeks proposes a change of `small_step_kcal`.

## User Stories

1. As the user, I want a block review every 5 weeks (my setting) from the phase start, so that I see how the block went.
2. As the user, I want to end a block early by saying so, so that the review follows my real blocks.
3. As the user, I want the block review to give evidence-based advice in words, a deload week included, but never a proposal.
4. As the user, I want a phase review every 10 weeks and at every phase end, with progress vs plan, the maintenance estimate, the waist trend, photos, a goal check and what's next.
5. As the user, I want drifted run discount or wrestling kcal proposed as calibration changes at the phase review.
6. As the user, I want to be asked what comes next when a phase ends.
7. As the user, I want a body-fat estimate from my photos at every photo check-in, with my own estimate winning.
8. As the user, I want mini-cut / end-of-bulk advice near 23–24 % body fat, as advice only.
9. As the user, I want to start a cut by picking a level (conservative, moderate, aggressive) or by giving a goal and a date.
10. As the user, I want a warning when I pick aggressive or a goal needs more than moderate.
11. As the user, I want the cut's start kcal from the maintenance estimate minus the deficit, shown for me to confirm.
12. As the user, I want a mini-cut as a cut with an end date.
13. As the user, I want the weekly cut decision to steer within ±40 % of the target rate: stalled → less food or more steps, too fast → a bit more food, no adherence → no change.
14. As the user, I want cut macros at 2.5 g/kg protein and 0.6 g/kg fat.
15. As the user, I want a simple maintenance phase that holds my weight within ±0.1 kg a week.
16. As the user, I want the reviews stored and visible on the web page.

## Implementation Decisions

- **Reviews** (features `block_review.py`, `phase_review.py`, `photo_review.py`, new):
  - **Facts, numbers and schedule:** computed in code. The model writes the text with `COACH_DECISION_MODEL`, from skills `block-review`, `phase-review` and `photo-review`.
  - **Storage:** reviews are stored in a `reviews` table (kind, phase, period, facts JSON, text, created_at) and sent in Telegram. Each one is once-keyed, so a review never goes out twice.
  - **Block schedule:** block n ends on phase start + n × `block_weeks` weeks (a setup value with history, follow-ups spec 03). "Block done" is a chat tool `end_block(reason)` that ends the current block today and restarts the count.
  - **Block facts:** the strength trend and per-lift statuses over the block, stalls, the deload signal, and sessions done against planned. Session volume over 20 sets a session or 4 sets per muscle a session, from Hevy sets; the muscle comes from Hevy's exercise template where available, otherwise left out.
  - **Phase review:** every 10 weeks from the start (`phase_review_weeks`, core param) and on phase end (follow-ups spec 01, ending triggers it).
    - **Facts:** weight against the band and the time goal, the strength trend, the maintenance estimate, waist, the photo-review estimates, and the calibration drift.
    - **Calibration drift:** the run discount comes from Strava kcal against the trend-implied activity; the wrestling kcal likewise.
    - **Calibration proposals:** through the existing calibration proposal path, approved in Telegram.
  - **Photo review:** runs after a photo set arrives. The model gets the current set and the most recent set at similar leanness (body fat within ±2 %, or the phase start set) as images, plus the waist trend.
    - **Storage:** it stores `body_fat_estimate_pct` with its source (model or user). A user-given value (chat tool `record_body_fat`) wins for its date.
    - **Mini-cut advice:** in a bulk, an estimate at or above `bulk.body_fat_advice_pct` (23) triggers the advice. The advice goes out at most once per 4 weeks.
  - **Web:** the Week page shows a review sent in its week, collapsed like the weekly report. Setup › Measurements lists the body-fat estimates.
- **Cut** (skill `phase-cut`, params and schema finalized; phase start accepts it):
  - **Setup values:** `cut_level` (conservative / moderate / aggressive) or `goal` {weight_kg | body_fat_pct, date}, and an optional `end_date` (mini-cut).
  - **Deficit:** from the level, or from the goal: the needed rate × 7,500 / 7, capped at 1,000.
  - **Band:** the target rate × (1 ± 0.4).
  - **Weekly decision:** reuses the A–E core, with the cut's scenario mapping from the doc (target met / stalled + adherence / stalled without adherence / too fast). The decision guard (follow-ups spec 05) applies symmetrically. The step is 100–200 kcal by the distance from the band; activity is offered as an alternative in the text.
  - **Macros:** protein 2.5 g/kg and fat 0.6 g/kg (floor).
  - **Glycogen window:** none for a cut started from maintenance or a bulk (a water drop is expected in week 1; week 1 is not judged).
  - **End date:** reaching `end_date` asks to end the phase (the follow-ups end card).
- **Maintenance** (skill `phase-maintenance`): band ±0.1 kg a week, drift ±0.2 kg a week for 2 confirming weeks → a `small_step_kcal` change toward flat; macros as the bulk's.
- **Phase start:** the preview shows the level, deficit, target rate and band for a cut. A cut warns on aggressive, or when the goal needs more than moderate.

## Testing Decisions

- Through the Coach seam with the fake model client:
  - the block schedule and "block done";
  - block facts (stalls, deload signal, volume over the limits);
  - the review once-keys;
  - the phase review every 10 weeks and on end;
  - calibration drift producing a proposal;
  - photo review picking a like-for-like set, and a user estimate winning;
  - mini-cut advice at the threshold, at most once per 4 weeks;
  - cut start from a level and from a goal (cap and warning);
  - the cut band and its decisions (stalled with and without adherence, too fast, on target);
  - cut macros;
  - maintenance drift.
- Skills validator: new skills, params and schemas. Examples are updated.
- `docker compose run --rm test` green.

## Out of Scope

- Replay tests (backlog).
- Training-plan proposals from the block review (advice only).
- Fine-tuning maintenance beyond the spec's numbers.

## Further Notes

- **Not in the docs:** the ±40 % tolerance, "too fast → +100 kcal" and the like-for-like rule of ±2 % body fat are my choices, confirmed with the user where noted. The docs give only the deficit levels and target met / stalled.
- **Blocked by:** cut and the phase review need the follow-ups spec's ending a phase (01) and setup history (03). The decision guard (05) is reused by the cut.
