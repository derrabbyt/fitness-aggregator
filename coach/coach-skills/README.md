# Coach skills package

Skills, parameters and data contracts for the personal coaching agent described in
`SPEC.md`. It lives in the coach project (`coach/coach-skills`), ships in the image,
and is read at runtime by `fa_coach/skills.py`. `tools/validate.py` runs as part of
`docker compose run --rm test`.

**Split of responsibility (SPEC: Implementation approach)**

- **Code** syncs MyFitnessPal into the database, computes every number (the *facts*), runs
  the scheduler and Telegram buttons, and enforces guardrails in `propose_change`.
- **Skills** make the decisions and do all interpretation and writing.
- **The model never calculates.** It reads facts and returns structured output. (Only exception: the kcal of a reported session code can't estimate, stored as `model_estimate`.)

```
coach-skills/
├── README.md                 this file
├── skills/                   one folder per skill, each with SKILL.md
│   ├── coach-core/           always loaded; hard rules; params.yaml (phase-independent numbers)
│   ├── phase-reverse-bulk/   active phase: A–E table; params.yaml
│   ├── phase-cut/            cut / mini-cut: level or goal → deficit, band ±40 %; params.yaml
│   ├── phase-maintenance/    hold weight: flat band, drift → small step; params.yaml
│   ├── phase-start/          "start reverse" command → setup → preview → confirm
│   ├── weekly-decision/      facts → verdict JSON
│   ├── weekly-report/        verdict → Telegram report
│   ├── evening-recap/        daily, usually silent
│   ├── training-feedback/    after a logged session
│   ├── new-exercise/         classifies an exercise that first shows up in Hevy
│   ├── block-review/         end of each training block
│   ├── phase-review/         every few weeks and at phase end
│   ├── photo-review/         photo check-ins (optional)
│   ├── context-log/          notes → tagged context notes
│   └── coach-chat/           every free-text message in the coach chat
├── schemas/                  JSON Schemas (the contract) + TOOLS.md
├── examples/                 valid example facts + verdict
├── tests/                    labeled-weeks template for replay testing
└── tools/validate.py         checks schemas, params, examples, skill frontmatter
```

## Which skills each job loads

Every call loads `coach-core` first, then the **active phase skill** (from
`week.phase_id`) when a phase is active, then the task skill. Without an active phase (none
started yet, or the last one ended) the prefix is `coach-core` alone: training feedback and
chat still run then. Parameters: code merges `coach-core/params.yaml` with the active phase's
`params.yaml` (phase wins on equal keys; core params alone without a phase) and passes the
result as `params` inside the facts.

| Job / trigger | Task skill(s) | Input | Output |
| --- | --- | --- | --- |
| Weekly check-in, step 1 (active phase only) | weekly-decision | `weekly_facts` | `weekly_verdict` → code calls `propose_change` if a proposal is set |
| Weekly check-in, step 2 | weekly-report | facts, verdict, proposal result, changes applied, deferred items, due | `coach_message` |
| Evening (after reminder time, active phase only) | evening-recap | `daily_facts` (evening) | `coach_message` |
| Lifting session synced (with or without a phase) | training-feedback | `daily_facts` (training) | `coach_message` |
| Unclassified exercise in a synced session (during a phase) | new-exercise | new exercises + those already classified, tool `classify_exercises` | text (counts toward the daily limit, else deferred to the weekly report) |
| End of training block (every `reviews.block_weeks` weeks from the phase start; `end_block` ends one early) | block-review | `block_facts` | `coach_message` (code sends `text` once, no buttons; its own summary without a usable answer) |
| Every few weeks / phase end | phase-review | `phase_summary` | `coach_message` (+ calibration proposals via tool) |
| Photo set received (active phase, photos on; no new photo for 10 min) | photo-review | the new set + the like-for-like set code picked (images), latest estimate, waist trend | `photo_review` (code stores the estimate, sends `notes` + the range as the photo review; code sends the body-fat advice) |
| Coach chat message | coach-chat + context-log (others via `load_skill`) | message + tools | text reply |
| "start …" command, and every message while that setup is open | phase-start (target phase skill in the prefix) | message + `setup` (recorded, still needed, prefill from history, Hevy exercises with their classification, limits) + tools | text; after `start_phase` code sends the preview card with confirm / edit buttons |

Code-only rules (no model call): refusing a draft phase with TO DECIDE values, the phase-start
preview card and its buttons, weigh-in outlier marking, missing-log reminder (one per
day), data-freshness check, waist/photo due dates, applying approved proposals, setting the
MyFitnessPal goal, and the day questions ("is that all you ate?", "real or a typo?"), which
run with or without a phase.

Prompt layout per call: stable cached prefix (coach-core + phase skill + tool definitions),
then the task skill, then a short state snapshot and the input JSON. Chat keeps only a
short history.

## Contracts

| Schema | Producer → consumer |
| --- | --- |
| `weekly_facts` | code → weekly-decision, weekly-report |
| `block_facts` | code → block-review |
| `weekly_verdict` | weekly-decision → code (stored with its facts; drives confirmation counting) |
| `proposal` | `propose_change` tool → store → buttons |
| `daily_facts` | code → evening-recap, training-feedback |
| `coach_message` | message-writing skills → Telegram sender |
| `context_note` | context-log → store → all facts |
| `photo_review` | photo-review → store → facts |
| `phase_summary` | code → phase-review |
| `phase_setup` | phase-start → `start_phase` tool |
| `core_params`, `phase_params` | validate the params.yaml files |
| `web_*` | code (read models, `fa_coach/views.py`) → the web page via `/api/coach/` (no model involved) |

Tools and the exact guardrail checks: `schemas/TOOLS.md`.

Field names are suggestions. If Claude Code renames something to fit the codebase, it
changes the schema, the skills that reference it, the examples, and reruns
`tools/validate.py` in the same commit.

## Rules for editing

- **Numbers only in `params.yaml`.** Skills refer to keys by name. `tools/validate.py`
  fails if a phase SKILL.md contains a number outside backticks.
- **Rule ids** (`WD-…`, `RB-…`, `CORE-…`) are stable; verdicts cite them, replay tests can
  check them. Rename only together with the tests.
- After every skill or params edit, rerun the labeled weeks (`tests/`).

## Assumptions (not decided in SPEC.md – confirm or change)

| Where | Value | Why it's needed |
| --- | --- | --- |
| `decisions.far_off_margin_kg_per_week` | 0.1 | SPEC says ~100 kcal "slightly outside", ~200 "far off" but doesn't define "far" |
| `data.sync_max_age_hours` | 36 | stale-data check needs a threshold |
| `data.weight_outlier_kg`, `data.weight_outlier_window_days` | 3.0 kg vs the median of the weigh-ins within 3 days either side (user: only clear typos are dropped; normal spikes stay in the average, the scale records every weigh-in) | SPEC says outliers are flagged, not how |
| `data.implausible_intake_factor` | 2 × the day's target; code asks **Real** / **Typo, I'll fix it in MFP** | SPEC asks about implausible entries (e.g. 12,000 kcal) without a threshold |
| `data.partial_day_share` | 0.5 × the median of the other logged days within 3 days either side (the day's target when fewer than 3); code asks **That's all I ate** / **I'll log the rest** | MFP can't tell a partly logged day (e.g. 158 kcal) from a complete one; unconfirmed, such a day is left out of the maintenance estimate, logging completeness and adherence (user decision 2026-11-10: the user confirms days, the coach never writes to MFP) |
| `training.deload_min_lifts_declining`, `training.decline_sessions_for_deload` | 2 counting lifts, 2 sessions in a row | SPEC says "several lifts declining" |
| `training.big_drop_pct_ask_reset` | 15 (% estimated-1RM drop vs the best recent session) | when code asks "was this a reset?" (training feedback; buttons, exempt from the daily limit) |
| `training.rep_range` | 4–20 | a session's performance = its heaviest working set with this many reps (warm-ups never count) |
| `training.e1rm_same_band_pct` | 1 | only when load and reps move in opposite directions: estimated 1RMs (Epley) within ±1 % are "same" (more load or reps and neither less is always improved) |
| `training.bodyweight_same_load_kg` | 1.0 | bodyweight lifts: a change in effective load that comes only from bodyweight is the same load unless the 7-day trend moved by at least 1 kg since the compared session (user decision) |
| `training.stall_sessions` | 3 | a stall = this many sessions in a row without progress |
| `training.strength_trend_days` | 28 | the web page's strength trend (Home and Training; `fa_coach/strength_trend.py`): each day's point is the mean over the counting lifts trained in the 28 days ending that day of the lift's latest estimated 1RM (effective load for bodyweight lifts) as % of its first one there (after its latest baseline reset; a lift needs 2 sessions there); the rate is each such lift's change per week of its own span (first session in the window or its reset to its latest one, at least 7 days), averaged over the lifts, flat within ±`e1rm_same_band_pct` (user decision 2026-11-10, reworked in ticket 14 and the code review) |
| `training.min_sessions_for_compare` | 2 (the judged session included) | the first session only starts a lift's history |
| `training.compare_best_of_last_sessions` | 3 | SPEC says "best of last 2–3" |
| `activity.met_by_activity` | running 8.0, cycling 7.5, swimming 6.0, football 7.0, basketball 6.5, tennis 7.0, hiking 6.0, walking 3.5, rowing 6.0, martial_arts 6.0 (grappling, BJJ, boxing …; wrestling and lifting use their setup values instead) | estimating kcal for sessions reported without kcal (MET × 7-day trend weight × hours); conservative "general" values in the style of the Compendium of Physical Activities. Other activities, or no trend weight yet: the model's own estimate, stored as `model_estimate` |
| `steps.kcal_per_step_at_70kg`, `steps.share` | 0.04 kcal per step at 70 kg (× trend weight / 70), 75 % counted | step kcal on top of base at the step goal (user decision: steps are live activity) |
| `steps.not_tracked_below` | 2,500 raw steps | below it the phone or watch wasn't carried: the day is not tracked (counted at the average, no step adjustment) and left out of averages |
| `steps.run_steps_per_km` | 1,200 | run steps are removed from the day's steps (runs count through Strava), as are reported sessions with a distance |
| `steps.step_goal` | 10,000 (setup value `step_goal` overrides it, changeable in chat) | where "0" step kcal is shown; doesn't change the energy the user gets |
| `nutrition.macro_reference_weight` | trend_7d | which weight g/kg uses; recalculated weekly |
| `decisions.prediction_miss_kg` | 0.3 | a weekly prediction error above this is a miss (log check, lower confidence) |
| Adherence-gate weeks | skipped like unusable weeks for confirmation (code records the skip with each stored verdict) | SPEC says no changes when adherence fails, not how they count |
| Sport-load weeks | a week with a `sport_load` context note gives no C/D call and is skipped for confirmation (neither counts nor breaks a streak) | SPEC says no C or D proposals from them |
| Cut weight classes | `above_band` = losing too slowly, `below_limit` = too fast | signed band; numbers still TO DECIDE |
| Maintenance | macros as the bulk's; drift beyond the limits for `decisions.confirmation_weeks` → `small_step_kcal` toward flat; small drift stored as hold | spec 2026-11-12 (kept small) |

## Spec coverage

| SPEC.md section | Where it lives |
| --- | --- |
| Core design, phase start inputs | coach-core, phase-start, `phase_setup` |
| Scheduled cadence | job table above; evening-recap, training-feedback, weekly-*, block-review, phase-review, photo-review |
| A–E decision logic + definitions | phase-reverse-bulk (table), weekly-decision (procedure), params |
| Nutrition engine | phase params `macros`, core `nutrition`, RB-MACROS (code computes) |
| Reverse and bulk settings | phase-reverse-bulk + params |
| Training data rules | `weekly_facts.training`, training-feedback, block-review, context-log (resets/pauses) |
| Photos and measurements | photo-review, RB-SOFT, RB-RECOMP, CORE-PHOTOS-OPTIONAL |
| Triggers | weekly-decision step 6 flags, evening-recap, training-feedback |
| Calibration and guardrails | `maintenance_estimate`, `prediction_*`, TOOLS.md guardrails, phase-review calibration |
| On-demand behaviours, reports | coach-chat, weekly-report, `coach_message` |
| Other phases | phase-cut, phase-maintenance |
| Dropped / left out | coach-core "Out of scope" |
