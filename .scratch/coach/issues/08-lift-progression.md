# 08: Lift progression in the weekly decision

**What to build:** Weekly facts now include gym progression, so the full A–E table applies. Each tracked lift is compared with the best of its last 3 sessions, using its own sessions whenever they happened. Stalls, the deload signal, new baselines and paused exercises are computed in code.

**Blocked by:** 07 (Weekly check-in: facts, verdict, report)

**Status:** ready-for-agent

- [x] Per tracked lift: status improved / same / declined / new baseline / paused vs the best of up to 3 previous sessions (at least 2 needed), counted only if trained within the recency window
- [x] Progress = more load or reps at the same execution; micro-progressions count; for dips, pull-ups and similar, bodyweight gained counts as added load (effective load)
- [x] `progression_met` is true when at least the configured share of counted lifts improved, null when no lift could be counted
- [x] No-progress streaks, stalls (3 sessions without progress), the deload signal (2+ lifts declining over 2+ sessions), possible resets (load drop of 15%+), session volume and PRs are computed
- [x] Baseline resets and pauses stored by later tickets are respected (a reset starts a new baseline; a paused exercise isn't judged)
- [x] The weekly report's training section shows how many tracked lifts improved, PRs, stalls and deload signals
- [x] Tests cover improvement, same, decline, a bodyweight lift, a lift not trained within the window, a stall, a deload signal, and A–E outcomes B, C and D end to end with a scripted verdict

## Decisions (user, 2026-11-09) — these override the text above where they differ

**Revised (later the same day): no importance weights.** Each exercise is classified `counts` or `excluded` instead; the two weight bullets below are replaced by:
- **Counts** (default): compounds, machines and most bigger isolation work (leg curl, leg extension, flys, rows, …). Only these decide `progression_met`: at least the configured share (half) of counted exercises improved vs the best of their last 3 sessions, one exercise one vote; null when none could be counted.
- **Excluded**: exercises that typically stall for long or aren't meant to progress (prehab/rehab or slow movers: lateral raises, tibialis raises, Copenhagen plank, hip flexor raises, abs, plyometrics like pogo hops / box jumps). Still logged, PRs still named; no effect on A–E and no stall flags.
- The model classifies each exercise (its judgement, stored per exercise), the coach shows the list at phase start and when a new exercise first appears, and the user can flip any in chat.

Original decisions (weights superseded):

- **Every exercise logged in Hevy is tracked** (the user logs only hypertrophy work). No picking tracked lifts at phase start; the user can exclude an exercise in chat. Change ticket 05's tracked-lifts setup step accordingly (phase start shows the weights instead of asking which lifts).
- **Importance weight 1–3 per exercise**, set by the model's judgement (compound/main = 3, secondary = 2, small/prehab like tibialis raise, Copenhagen plank, abs = 1), shown to the user at phase start and when a new exercise first appears, changeable in chat. Stored per exercise; code uses it.
- **`progression_met`**: the improved exercises' weights sum to at least half (the configured share) of the total weight of counted exercises; null when nothing could be counted.
- **Session performance** = heaviest working set with 4–20 reps (warm-ups never count; sets outside 4–20 ignored for progression). Same load: more reps = improved, same = same, fewer = declined. Different load: compare estimated 1RM (Epley, w × (1 + r/30)); within ±1 % = same, above = improved, below = declined. Bodyweight lifts use effective load (bodyweight delta added).
- **First session of a new exercise** starts its history: no PR, not judged.
- **Alternatives** (e.g. pull-ups vs lat pulldown) are separate exercises, each with its own history; no grouping.
- **After a break** longer than the recency window (14 days): the first session back is not judged; the next one is compared with the best of the last 3 sessions, which include the pre-break sessions.
- **Other gym / other machine**: a context note for that day (e.g. tag `other_location`, set via chat) means that day's sessions are not judged, are not used as a baseline, and trigger no reset question or PR. Not logging, or logging under a separate Hevy exercise, needs no special handling.

## Comments

- Code: `fa_coach/progression.py` (judging; read API `session(coach, session_id)` for ticket 12,
  `week(...)` for the facts, `exercises(...)`; writes `classify`, `set_paused`, `mark_reset`),
  `features/lifts.py` (facts hook, tools `classify_exercises` / `get_tracked_exercises`, job
  `new-exercises`), migration `08_lifts.sql` (`exercise_settings`, `baseline_resets`).
- Ticket 05's `tracked_lifts` is retired: removed from the phase-setup schema and
  `record_setup_value`; the migration strips it from stored phases, setups and previews.
  Phase start now lists `exercise_classification` in `still_needed` while any exercise in the
  16-week Hevy history is unclassified; the preview card lists counting and excluded lifts.
- Unclassified exercises count (the default). A new exercise during a phase triggers the
  `new-exercise` skill (new) once per day until classified; its message counts toward the daily
  limit and is deferred to the weekly report when the limit is reached.
- Interpretations: `min_sessions_for_compare: 2` now counts the judged session (the first only
  starts the history, per the decision). "Best of the last 3" picks the highest e1RM. Literal
  ±1 % band: a small load jump at the same reps (e.g. 100 → 100.5 kg × 8) is "same", not a
  micro-progression. Bodyweight = 7-day trend weight, else the latest weigh-in; Hevy types
  `bodyweight_reps`, `reps_only`, `bodyweight_weighted` add bodyweight, `bodyweight_assisted_reps`
  subtracts the assistance. A pause or another-gym note without `exercise_id` applies to every
  exercise that day; injury / pain / baseline_reset notes suppress `possible_reset`. Excluded
  lifts are listed (with PRs) but give no stalls and don't count toward the deload signal.
  Sessions without a set in 4–20 reps (e.g. planks logged by duration) are ignored.
- Weekly facts `training` gained `improved_lifts`, `stalls`, `declining_lifts`, `prs`,
  `excluded_lifts`, `lifting_sessions`; lifts gained `counts`, `classification`,
  `not_judged_reason`, `counted`, `stalled`; status `not_judged`; set summaries `e1rm_kg`.
  `max_sets_per_muscle_in_a_session` stays null (Hevy muscle groups aren't synced).
- New core params `training.rep_range`, `training.e1rm_same_band_pct` (schema + README
  assumptions). Context-note tag `other_location` (schema, context-log skill, example);
  `tools/validate.py` now checks that tags code acts on are in the schema and the context-log skill.
- The weekly report's code fallback has a training line (`weekly_checkin.training_summary`).
- Left for ticket 12: `mark_baseline_reset` / `set_exercise_paused` tools, the training-feedback
  skill wording (status `not_judged`, `counts` instead of `tracked` in daily facts).
