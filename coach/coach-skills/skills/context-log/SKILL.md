---
name: context-log
description: Turns a free-form note from the user (sick, travel, wrestling camp, creatine, knee hurts, felt flat, ate out) into a stored context note with dates and tags. Loaded by default in the coach chat. Output of each note follows context_note.schema.json via add_context_note.
---

# Context log

The user can send context any time, in any form, with no fixed format. Store it so every
later decision can respect it.

## Steps

1. **CL-DETECT** – Treat a message as a context note when it tells you something about the
   user's life, body or training that the data alone wouldn't show. A question or a command
   is not a note (but can contain one).
2. **CL-STORE** – Call `add_context_note` with (code stores the user's message itself as
   the note's `text`, unchanged):
   - `applies_from` / `applies_to`: the dates it concerns ("since Tuesday", "this weekend",
     "today"), resolved against `today` in the state; today if unclear; `applies_to` equal
     to `applies_from` for a single day, null for something ongoing
   - `tags`: every tag from the schema that fits; a heavy sport week (camp, tournament,
     double sessions) gets `sport_load`; training at another gym or on other machines that
     day gets `other_location` (that day's lifting sessions are then not judged, not used as
     a baseline, and give no PR or reset question); `injury`, `pain` and `baseline_reset`
     for those notes (they also stop the "was this a reset?" question for that day)
   - `exercise_id` for injury, pain, reset or other-location notes about one exercise
     (an `other_location` note without it covers every exercise that day)
   - `suggest_unusable`: `yes` for illness or travel across several days, `maybe` for
     shorter disruptions, `no` for normal life (one restaurant meal, one late night)
   - `follow_up_question`: one short question only if something essential is unclear
3. **CL-ACT** – Some notes need an action tool in addition:
   - injury or pain affecting an exercise → ask whether to pause tracking for it, then
     `set_exercise_paused`
   - technique change, ROM change or exercise swap → `mark_baseline_reset` (confirm the
     exercise and date first if ambiguous)
   - "lateral raises should count" / "don't count abs" → `classify_exercises` (find the id
     with `get_tracked_exercises`)
   - a planned session that didn't happen → `set_session_status` skipped; an extra session
     → `set_session_status` extra with its type and either the user's kcal or the activity
     and duration (code estimates; see coach-chat CC-PLAN)
   - "this is a heavy week" / "camp" → the note itself carries the tag `sport_load` and
     covers the heavy days; "not actually heavy" → `get_context_notes`, then
     `delete_context_note` for that note
   - a goal change → note it and mention it at the next phase review; a phase change needs
     the phase-start command
4. **CL-REPLY** – Confirm in one short line what was noted and its effect if any ("Noted:
   sick Mon–Wed; that week may not count for decisions"). No advice.

## Rules

- **CL-NO-JUDGE** – Never comment on whether the note is good or bad.
- **CL-SUPPLEMENTS** – Supplement or medication notes are recorded only to explain weight
  shifts (e.g. creatine water); no advice about them.
