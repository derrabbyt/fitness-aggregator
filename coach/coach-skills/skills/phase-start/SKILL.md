---
name: phase-start
description: Handles a Telegram phase-start command such as "start reverse" and every message while that setup is open. Collects missing setup values, calls start_phase for a code-computed week-1 preview; code then sends the preview card with confirm and edit buttons. Loaded with coach-core and the target phase skill (not the old one).
---

# Phase start

A phase starts only with an explicit command from the user. The previous phase ends when the
user confirms the new one (ending is always the user's call).

Code already refused draft phases with values marked TO DECIDE before you are called, and
code handles "cancel". Every message while the setup is open comes to you, with `setup` in
the input:

- `recorded`: values stored so far; `still_needed`: keys `start_phase` still needs.
- `prefill`: what code read from the synced history, each `{value, source}` or
  `{value: null, missing}` (last diet intake, starting trend weight, maintenance estimate).
- `exercises`: every exercise in the Hevy history (`exercise_id`, `title`, Hevy type,
  sessions, `classification`: `counts`, `excluded` or null = not classified yet);
  `plan_exercise_lists`: the exercise lists of the saved training plan.
- `limits`: ranges values must respect; `previous_phase_setup`: values of the last phase.

## Steps

1. **PS-COLLECT** – Fill what `still_needed` lists. Show prefilled values with their source
   and ask the user to confirm them; record a value only once the user confirms or gives it.
   Values in `previous_phase_setup` may be offered for reuse the same way. Ask only for
   what's missing, a few items per message:
   - which lifts count (`exercise_classification` in `still_needed`): every exercise logged
     in Hevy is recorded; don't ask which to track. Classify each unclassified item of
     `exercises` yourself with `classify_exercises`: `counts` (the default: compounds,
     machines, most bigger isolation work) or `excluded` (prehab/rehab and slow movers –
     lateral raises, tibialis raises, Copenhagen plank, hip flexor raises, abs, plyometrics
     like pogo hops and box jumps). `plan_exercise_lists` can help. Show the user the list
     (counting / excluded) and flip any they disagree with. Code works out bodyweight
     exercises from Hevy.
   - starting calories (last diet intake, daily average), starting trend weight,
     maintenance estimate from the last diet weeks. When `prefill` has no value, say why
     (its `missing`) and ask the user for the number.
   - run kcal discount, wrestling kcal per session, lifting kcal per session (counted for each
     lifting session that shows up in Hevy)
   - fat start in g/kg within `limits.fat_g_per_kg_start`
   - phase specifics: reverse_bulk the week-1 increase within `limits.week1_increase_kcal`
     (suggest the lower end)
   - optional time goal (`time_goal_weeks`), photos on/off, waist at start; record null when
     the user has none
   - logistics: weekly check-in day and time (`logistics.weekly_checkin`, e.g. `sun 18:00`),
     evening reminder time, daily message limit, what "a while" means for the step floor
     (`logistics.soft_floor_min_days`)
   - the training plan is the saved one (`get_training_plan`); changes go through
     `update_training_plan`
   Record each value with `record_setup_value` as soon as it's given. If it comes back with
   an error, tell the user what's wrong in one line and ask again.
2. **PS-PREVIEW** – When `still_needed` is empty, call `start_phase`. Code sends the preview
   card right after your reply: average daily target and the MyFitnessPal goal (a rest
   day: base maintenance + surplus; activity comes on top), targets on a
   rest / lifting / run / wrestling day, macros, the glycogen-window note, the counting and
   excluded lifts, and the confirm and edit buttons. Don't repeat or compute any of these numbers; reply with one short line
   (e.g. what the first weeks look like, per the phase skill) or nothing.
3. **PS-CONFIRM** – Nothing changes until the user taps confirm. Confirm makes the phase
   active, stores its targets, sets the MyFitnessPal goal and marks the phase's first change
   as applied. Edit returns here: record the changed values and call `start_phase` again.

## Rules

- **PS-NO-DEFAULTS** – Never fill a setup value with a guess. Every number comes from
  `prefill` (confirmed by the user) or from the user. If the user says "use the usual",
  reuse the stored value and name it. (Classifying exercises is your judgement, not a
  setup value; the user sees and can flip it.)
- **PS-CHANGE-MIDWAY** – After the start, `record_setup_value` changes logistics, photos,
  time goal and waist at start; `classify_exercises` flips an exercise any time. Calibration values (run discount, wrestling
  kcal, lifting kcal) go through `propose_change`; start values are fixed for the phase.
