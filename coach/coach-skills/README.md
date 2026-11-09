# Coach skills package

Skills, parameters and data contracts for the personal coaching agent described in
`SPEC.md`. It lives in the coach project (`coach/coach-skills`), ships in the image,
and is read at runtime by `fa_coach/skills.py`. `tools/validate.py` runs as part of
`docker compose run --rm test`.

**Split of responsibility (SPEC: Implementation approach)**

- **Code** syncs MyFitnessPal into the database, computes every number (the *facts*), runs
  the scheduler and Telegram buttons, and enforces guardrails in `propose_change`.
- **Skills** make the decisions and do all interpretation and writing.
- **The model never calculates.** It reads facts and returns structured output.

```
coach-skills/
├── README.md                 this file
├── skills/                   one folder per skill, each with SKILL.md
│   ├── coach-core/           always loaded; hard rules; params.yaml (phase-independent numbers)
│   ├── phase-reverse-bulk/   active phase: A–E table; params.yaml
│   ├── phase-cut/            draft
│   ├── phase-maintenance/    draft
│   ├── phase-start/          "start reverse" command → setup → preview → confirm
│   ├── weekly-decision/      facts → verdict JSON
│   ├── weekly-report/        verdict → Telegram report
│   ├── evening-recap/        daily, usually silent
│   ├── training-feedback/    after a logged session
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
`week.phase_id`), then the task skill. Parameters: code merges `coach-core/params.yaml` with
the active phase's `params.yaml` (phase wins on equal keys) and passes the result as
`params` inside the facts.

| Job / trigger | Task skill(s) | Input | Output |
| --- | --- | --- | --- |
| Weekly check-in, step 1 | weekly-decision | `weekly_facts` | `weekly_verdict` → code calls `propose_change` if a proposal is set |
| Weekly check-in, step 2 | weekly-report | facts, verdict, proposal result, changes applied, deferred items, due | `coach_message` |
| Evening (after reminder time) | evening-recap | `daily_facts` (evening) | `coach_message` |
| Lifting session synced | training-feedback | `daily_facts` (training) | `coach_message` |
| End of training block | block-review | block's `weekly_facts` list | `coach_message` |
| Every few weeks / phase end | phase-review | `phase_summary` | `coach_message` (+ calibration proposals via tool) |
| Photo set received | photo-review | photos + previous set + previous estimate | `photo_review` (code sends `notes`) |
| Coach chat message | coach-chat + context-log (others via `load_skill`) | message + tools | text reply |
| "start …" command, and every message while that setup is open | phase-start (target phase skill in the prefix) | message + `setup` (recorded, still needed, prefill from history, lift options, limits) + tools | text; after `start_phase` code sends the preview card with confirm / edit buttons |

Code-only rules (no model call): refusing a draft phase with TO DECIDE values, the phase-start
preview card and its buttons, weigh-in outlier marking, missing-log reminder (one per
day), data-freshness check, waist/photo due dates, applying approved proposals, setting the
MyFitnessPal goal.

Prompt layout per call: stable cached prefix (coach-core + phase skill + tool definitions),
then the task skill, then a short state snapshot and the input JSON. Chat keeps only a
short history.

## Contracts

| Schema | Producer → consumer |
| --- | --- |
| `weekly_facts` | code → weekly-decision, weekly-report, block-review |
| `weekly_verdict` | weekly-decision → code (stored with its facts; drives confirmation counting) |
| `proposal` | `propose_change` tool → store → buttons |
| `daily_facts` | code → evening-recap, training-feedback |
| `coach_message` | message-writing skills → Telegram sender |
| `context_note` | context-log → store → all facts |
| `photo_review` | photo-review → store → facts |
| `phase_summary` | code → phase-review |
| `phase_setup` | phase-start → `start_phase` tool |
| `core_params`, `phase_params` | validate the params.yaml files |

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
| `data.weight_outlier_kg`, `data.weight_outlier_window_days` | 1.5 kg vs the median of the weigh-ins within 3 days either side | SPEC says outliers are flagged, not how |
| `training.deload_min_lifts_declining` | 2 | SPEC says "several lifts declining" |
| `training.big_drop_pct_ask_reset` | 15 | when the agent asks "was this a reset?" |
| `training.compare_best_of_last_sessions` | 3 | SPEC says "best of last 2–3" |
| `nutrition.macro_reference_weight` | trend_7d | which weight g/kg uses; recalculated weekly |
| `weight.prediction_miss` | error > band width | flags a missed weekly prediction without a new param |
| Adherence-gate weeks | skipped like unusable weeks for confirmation | SPEC says no changes when adherence fails, not how they count |
| Sport-load weeks | C/D become direction "hold", so an increase streak restarts | SPEC says no C or D proposals from them |
| Cut weight classes | `above_band` = losing too slowly, `below_limit` = too fast | signed band; numbers still TO DECIDE |
| Maintenance macros | reused from reverse_bulk | not decided |

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
| Other phases (draft) | phase-cut, phase-maintenance |
| Dropped / left out | coach-core "Out of scope" |
