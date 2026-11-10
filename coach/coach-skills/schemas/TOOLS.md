# Coach tools (contract for code)

Tools the coach model can call in the **coach chat** and in jobs that need them. All return
pre-aggregated JSON, never raw MyFitnessPal dumps. Names are suggestions; Claude Code can
rename them to fit the codebase as long as SKILL.md references are updated in the same change.

Rule for every write tool: **code validates, code applies.** The model only asks.

## Read

| Tool | Input | Returns |
| --- | --- | --- |
| `get_weekly_facts` | `iso_week` (optional, default the latest) | a stored check-in: `facts` (`weekly_facts.schema.json`), `verdict`, `rules_applied`, `counts_for_confirmation`, `skip_reason`, `code_adjustments` |
| `get_daily_facts` | `date` (optional, default today) | `daily_facts` (`daily_facts.schema.json`, kind evening) + `lift_sessions`: that day's Hevy sessions, each exercise judged |
| `get_lift_history` | `exercise_id`, `n_sessions` | sessions since last baseline: date, sets (load, reps), top set (effective load, e1RM), status, PR, streaks, notes |
| `get_tracked_exercises` | – | exercises in the synced Hevy history (16 weeks): id, title, Hevy type, bodyweight or not, sessions, last date, `classification` (`counts`/`excluded`/null = not classified yet, counts), paused |
| `get_context_notes` | `from`, `to` | list of `context_note.schema.json` |
| `get_targets` | – | active phase (week, glycogen window), current targets (base maintenance, surplus, expected counted activity, average daily target, MFP goal) + daily targets for the current week |
| `get_training_plan` | – | the saved plan in force today (sessions per weekday with ids, exercise lists) + this week day by day with the user's reports + upcoming lasting changes |
| `get_proposals` | `status` (optional) | list of `proposal.schema.json` |
| `get_coach_profile` | – | `{profile: {key: value}}`: short entries (preferences, known issues); also in every call's state snapshot |
| `load_skill` | `name` | SKILL.md of another skill from the index |

## Write

| Tool | Input | What code does |
| --- | --- | --- |
| `propose_change` | `type`, `delta_kcal` or `new_values`, `reason`, `source`, `based_on_week`, `is_phase_first_change`, `counter_of`, `returning_rejected_proposal_id`, `agent_disagrees` | Runs guardrails (below). Stores a `proposal` with status `open` or `blocked_by_guardrail` and returns it with `guardrail.violations`. Never applies anything. |
| `add_rejection_reason` | `proposal_id`, `reason` | Stores `user_reason` on a rejected proposal. |
| `add_context_note` | `context_note` without `id` / `created_at` / `text` | Stores the note with the user's message as `text` (unchanged); returns the stored note. A heavy sport week is a note tagged `sport_load` covering those days. |
| `delete_context_note` | `id` | Removes a wrong note (e.g. a `sport_load` week that wasn't heavy after all). |
| `mark_baseline_reset` | `exercise_id`, `reason` (`technique_change`/`rom_change`/`exercise_swap`/`other`), `date` (default today) | The exercise's first session on or after `date` starts a new baseline (not judged, no PR); returns that session's date (null = the next session). The training-feedback reset buttons do the same for their session. |
| `set_exercise_paused` | `exercise_id`, `paused`, `reason` | Injury pause on/off, only after the user agreed (an injury note alone never pauses). A paused exercise is logged but not judged: no PR, stall, reset question or progression vote. |
| `classify_exercises` | `exercises`: [{`exercise_id`, `classification` (`counts`/`excluded`), `reason`}] | Stores the model's classification (or the user's flip) per exercise; the id must be in the synced Hevy history. Only counting lifts decide `progression_met`, stalls and the deload signal; excluded ones are logged and their PRs named. Unclassified exercises count. |
| `set_session_status` | `date` (this or last week), `status` (`skipped`/`done`/`extra`/`clear`), `session_id` (planned session) or `type` + `name` (extra), `extra_id` (clear an extra); for done/extra kcal: `kcal` (the user's number only) or `activity` + `duration_min`, and `kcal_estimate` only when code can't estimate | One day only: a planned session skipped or done, an extra session, or a report undone. kcal order: the user's `kcal` (always wins, `reported`); code's estimate = `activity.met_by_activity` MET × current 7-day trend weight × hours (`estimated`); the model's own `kcal_estimate` when code can't (unknown activity, no trend weight; `model_estimate`). Wrestling and lifting without the user's kcal count their setup values. Missing duration → the tool says to ask once (or pass it if the description makes it obvious). Returns that day and `reported` {kcal, kcal_source, kcal_counted, say}. |
| `update_training_plan` | `days` (weekday → full session list), `exercise_lists` (name → items or null), optional `from` | Lasting change: a new plan version from `from` (default today, this week at the earliest); earlier days keep their plan. Returns the new plan. |
| `record_setup_value` | `key` (a `phase_setup` property, `logistics.<key>` for logistics), `value` | During a phase setup: stores the value as soon as it's given, validated against `phase_setup.schema.json` and the phase's params (fat within `macros.fat_g_per_kg_min..max`, week-1 increase within `start.week1_increase_kcal`); returns what's still needed (`exercise_classification` while an exercise in the Hevy history isn't classified). During an active phase: changes logistics, photos, time goal, waist at start; calibration values are refused (proposal), start values are fixed. |
| `start_phase` | – | Builds the setup from the recorded values, validates it, stores it as pending and returns a **week-1 preview** computed by code (average daily target, MFP goal, daily targets by day type, macros). Code sends the preview card with `confirm_phase_start` / `edit_phase_start`; the phase starts only on confirm (atomic claim, once); code then sets the MFP goal once and adds to the card whether MFP shows it (no model tool can set the MFP goal). |
| `update_coach_profile` | `patch`: `{key: value or null}` | Sets or (null) removes short entries; returns the whole profile. The reply tells the user what changed; `/profile` shows it. |

The plan is seeded once from the CSV in `coach/data/training_plan.csv` and afterwards
changes only through `update_training_plan` and `set_session_status`; the CSV is never re-read.

**Counted activity** (code, per day): Strava runs count at their kcal × `run_kcal_discount`
(HealthKit copies and HealthKit "Strength training" never count); a planned run marked done
counts with its reported kcal (discounted) only when Strava has no run that day. Each Hevy
session counts `lifting_kcal_per_session` (a planned lift marked done without a Hevy session
counts the same). Planned wrestling counts `wrestling_kcal_per_session` unless reported
skipped. Extras count with their stored kcal, whatever the source (runs discounted, so a run
without Strava estimated from its duration is discounted like a synced one); wrestling and
lifting extras without kcal count their setup values. Optional sessions that
didn't happen count nothing and need no report.

Buttons (`approve_proposal`, `reject_proposal`, `counter_proposal`, `confirm_phase_start`, …)
are handled by code directly; the model is only called afterwards if a reply needs writing.

## `propose_change` guardrails (code)

A proposal is `blocked_by_guardrail` if any of these hold:

1. `calorie_change` and `|delta_kcal| > decisions.max_change_kcal`, unless `is_phase_first_change`
   and the delta is within the phase's start range → `exceeds_max_change`.
2. Fewer than `decisions.confirmation_weeks` usable weeks since the last applied change
   (`confirmation_weeks_fast_lane` when the verdict's scenario is the phase's "too fast"
   scenario: reverse_bulk `E`, cut `too_fast`). The week after a change counts as week 1;
   for a change from a weekly check-in (or a counter to it) that is the week after the
   verdict week, whatever day the user approves → `lockout`.
3. Stored verdicts don't show the required consecutive usable weeks pointing the same
   direction → `confirmation_not_met`. A `user_counter` in the same direction as the
   proposal it replaces inherits that proposal's confirmation; a counter in the other
   direction, and any `user_request`, is checked normally. `phase_start` skips 2–4.
4. Same direction as the last rejected proposal and fewer than
   `decisions.rejected_return_weeks` usable weeks since the rejection still pointed that way
   → `rejected_return_too_early`.
5. `based_on_week` was unusable → `week_unusable`; weekly adherence failed → `adherence_gate`.
6. `calibration_change` with out-of-range values (`phase_setup.schema.json` ranges) or keys
   other than `run_kcal_discount`, `wrestling_kcal_per_session`,
   `lifting_kcal_per_session` → `invalid_values`.
7. `weekly_decision` only (the verdict's own proposal; user requests and counters keep
   1–5): the direction must be the one the phase's scenario calls for (reverse_bulk: C
   increase, E decrease, every other scenario no calorie change), and the size the one the
   trend calls for: `decisions.large_step_kcal` when the 7-day rate is
   `decisions.far_off_margin_kg_per_week` or more outside the band, else
   `decisions.small_step_kcal` (±25 kcal; a phase's first change keeps its start range)
   → `size_or_direction_mismatch`, saying what code expected.

Not a guardrail: other open proposals may coexist (no stacking rule). An identical open
proposal should be referenced, not duplicated (idempotency).

Each violation also gets a line in `guardrail.details`: `{violation, text, earliest_checkin}`
(what failed and the first weekly check-in that could pass it if the weeks until then count;
null when waiting doesn't help, e.g. a too-large change). The proposal is "based on" the
given `based_on_week`, else the replaced proposal's week (counters), else the latest stored
check-in. The "too fast" scenario per phase is in code (reverse_bulk `E`, cut `too_fast`).
A `calibration_change` is checked by 6 only.

On **approve** (one atomic claim, so a double tap applies once): apply delta to
`surplus_kcal` and the average daily target from today, macros at the current macro reference
weight, then set the MyFitnessPal goal to the new average daily target once, read it back,
never retry (a failed or uncertain write is reported; the coach targets stay as approved).
Other open calorie proposals become `superseded` (they were based on the old targets).
A calibration change updates the phase's setup value (counted from today) and recomputes
the targets from today as the phase start did: the expected counted activity moves by what
the new values change over the last 28 days; when maintenance includes activity, base
maintenance moves the other way, so the average stays and only the days' targets shift.
The surplus never changes, so it doesn't restart the lockout. If the average daily target
moved, the MFP goal is set once like a calorie change. The next weekly report lists the
change (`changes_applied`).
On **reject**: code asks for an optional reason; store it with `add_rejection_reason`.
On the **counter** button: code asks for the user's number; the proposal stays open
(`counter_awaited` in the state snapshot, for a day). A reply that is just a number
("+50", "make it 80") is code's: a bare number keeps the proposal's sign; a calibration
proposal with one value takes the number as that value. Code creates the proposal with
`source=user_counter`, `counter_of` set, and, if it differs from the coach's own proposal at
the root of the counter chain, says once on the new card what the coach would have chosen
(`agent_disagrees`). Any other reply goes to the chat (`propose_change` with
`counter_of`). When the counter is open, the old one becomes `superseded`; when it is
blocked, the old one stays open and the user is told which guardrail and when. Every tap removes that proposal's buttons from its cards
and shows the outcome (the counter tap changes nothing, so its buttons stay).
