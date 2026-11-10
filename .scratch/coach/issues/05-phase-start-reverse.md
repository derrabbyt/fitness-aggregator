# 05: Phase start: reverse

**What to build:** "start reverse" in the coach chat starts setting up the reverse-into-bulk phase. The coach prefills what it can read from the synced history (last diet intake, starting trend weight, maintenance estimate, main lifts from Hevy) and asks only for what's missing, a few items per message: tracked lifts, run discount, wrestling kcal, lifting kcal per session, fat start, week-1 increase, optional time goal, photos on/off, waist at start, and logistics (check-in day and time, evening reminder time, message limit, step-floor window). Code computes a week-1 preview; nothing changes until the user taps confirm.

**Blocked by:** 02 (Sync history from MFP and Hevy), 04 (Training plan in chat)

**Status:** resolved

- [x] The phase-start skill is loaded with the target phase skill; draft phases with undecided values are refused, listing what must be decided
- [x] Prefilled values come from code-computed history and are shown for confirmation, never guessed
- [x] `record_setup_value` stores each value as soon as it's given and validates it against the params and phase-setup schemas
- [x] A new setup value, lifting kcal per session, exists in core params, the phase-setup schema and the phase-start skill
- [x] `start_phase` stores a pending phase and returns a code-computed preview: average daily target, the MFP goal it will set, daily targets on rest / lifting / run / wrestling days, and macros (protein and fat in g/kg of the current 7-day trend weight, carbs as remainder)
- [x] The preview message explains the glycogen window and the expected early jump, and has confirm and edit buttons
- [x] Confirm makes the phase active, stores targets and marks the phase's first change applied; edit returns to collecting values; before confirm nothing is active
- [x] A second tap on confirm does nothing (atomic claim)
- [x] Tests cover a full start with a scripted model, refusal of a draft phase, edit-then-confirm, and that nothing is active before confirm

## Comments

- Code refuses a draft phase before any model call (any `draft: true` phase; the message lists the
  params keys marked TO DECIDE, read from the params.yaml comments by `SkillsPackage.undecided`).
- `start_phase` takes no input: it builds the setup from the values `record_setup_value` stored.
  Logistics keys are `logistics.<key>`. Optional values (time goal, waist) are recorded as null
  when declined, so `start_phase` knows they were asked. Logistics are required for a start
  (tickets 07/11 need them); `weekly_checkin` now has a pattern (`sun 18:00`).
- The preview card (numbers, glycogen note, buttons) is rendered by code, not the model; the model's
  reply goes out just before it. New phase param `glycogen_jump_kg: [1, 2]` (reverse_bulk) holds the
  "1–2 kg" from story 32.
- Prefill thresholds (code constants in `phases.py`): last diet intake = average of the logged days
  among the last 7 complete days (≥ 5 logged); trend weight = mean of non-outlier weigh-ins in the
  last 7 days (≥ 3); maintenance estimate = most recent run of 3–6 usable weeks (fully logged,
  ≥ `min_weighins_per_week`, no `suggest_unusable: yes` note, outside earlier glycogen windows).
  Otherwise the value is null with a `missing` reason and the coach asks.
- Base maintenance = maintenance estimate − average daily counted activity over the estimate's
  weeks (last 28 days when there is no estimate). Week-1 average target = last intake + week-1
  increase; surplus = average − base − that average activity (negative at the start of a reverse).
  The run-day target uses the median synced Strava run in that window, else is shown as "rest day
  + the synced run".
- Tracked lifts not in the Hevy history yet are stored by name with `exercise_id: null` (schema now
  allows null); ticket 08 should match them by title once they sync.
- Accessors for 06/07/11/13 in `fa_coach/phases.py`: `active`, `params` (core + phase + setup values,
  logistics in `messaging`), `setup_value`, `targets`, `set_targets`, `daily_target`, `macros`,
  `macro_reference_weight`, `trend_weight`, `phase_week`, `in_glycogen_window`,
  `maintenance_estimate`. Goal-write hook for 06: `@phases.on_confirmed`, run once after confirm.
- After the start, `record_setup_value` changes logistics, photos, time goal, waist and tracked
  lifts; calibration values are refused (proposal, ticket 10) and start values are fixed.
- Added `get_targets` (read tool) and a `phase` entry in the state snapshot.
