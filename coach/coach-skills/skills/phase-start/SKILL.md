---
name: phase-start
description: Handles a Telegram phase-start command such as "start reverse", "start cut", "start maintenance". Collects missing setup values, calls start_phase for a code-computed week-1 preview, and asks the user to confirm. Load with coach-core and the target phase skill (not the old one).
---

# Phase start

A phase starts only with an explicit command from the user. The previous phase ends at
that moment (ending is always the user's call).

## Steps

1. **PS-PHASE** – Identify the phase (`reverse_bulk`, `cut`, `maintenance`). If the target
   phase's params say `draft: true` and contain values marked TO DECIDE, stop: list those
   values and ask the user to decide them first. Don't start a draft phase with open values.
2. **PS-COLLECT** – Fill `phase_setup.schema.json`. Reuse values that already exist (from
   `get_targets`, `get_training_plan`, earlier setup) and show them for confirmation instead
   of asking again. Ask only for what's missing, at most a few items per message:
   - tracked lifts (the exercises that count for progression; offer the main lifts from the
     training log by name)
   - starting calories (last diet intake, daily average)
   - starting trend weight
   - maintenance estimate from the last diet weeks
   - training and sport plan (default week from the Google Sheet or the saved plan)
   - run kcal discount and wrestling kcal per session
   - fat start in g/kg within the phase's `macros.fat_g_per_kg_min`..`max`
   - phase specifics: reverse_bulk the week-1 increase within `start.week1_increase_kcal`
     (suggest the lower end); cut the deficit from `start.deficit_kcal`
   - optional time goal (`time_goal_weeks`), photos on/off, waist at start
   - logistics if never set: weekly check-in day and time, evening reminder time, message
     limit, what "a while" means for the step floor
   Record each value with `record_setup_value` as soon as it's given.
3. **PS-PREVIEW** – Call `start_phase` with the setup. Show the preview code returns: average
   daily target and the MyFitnessPal goal it will set, targets on a rest / lifting / run /
   wrestling day, macros. Don't compute any of these yourself.
4. **PS-EXPECT** – Say what the first weeks look like, from the phase skill (reverse_bulk:
   the glycogen window and the expected early jump; no weight-based decisions during it).
5. **PS-CONFIRM** – Buttons `confirm_phase_start` and `edit_phase_start`. Nothing changes
   until the user confirms. After confirmation code applies targets, sets the MyFitnessPal
   goal and marks the phase's first change as applied.

Output for the preview message: `coach_message.schema.json`.

## Rules

- **PS-NO-DEFAULTS** – Never fill a setup value with a guess. If the user says "use the
  usual", reuse the stored value and name it.
- **PS-CHANGE-MIDWAY** – The user can change setup values later in chat; that goes through
  `record_setup_value` (and `propose_change` for calibration values outside a phase start).
