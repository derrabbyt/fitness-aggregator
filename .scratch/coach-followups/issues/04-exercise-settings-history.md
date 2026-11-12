# 04: Exercise classification and pause as of the day

**What to build:** Migration `exercise_setting_changes (exercise_id, classification, paused, paused_reason, valid_from, created_at)`, seeded from `exercise_settings` with `valid_from = '0001-01-01'`. Changes (chat tools, web) add a row valid from the day made. `progression.lifts(coach, day)` and the strength trend use the setting in force on each session's day for judging, and on the shown day for "counts".

**Blocked by:** None

**Status:** resolved

- [x] Migration with seeding
- [x] Tests: a lift excluded later still counts on earlier weeks; a pause covers only its days
- [x] Tests green

Spec: `.scratch/coach-followups/spec.md`.

## Comments

- `24_exercise_setting_history.sql`: `exercise_setting_changes` (plus an `id` for same-day order), each row the exercise's whole setting from `valid_from`; seeded from `exercise_settings` at `0001-01-01`. `exercise_settings` stays as the latest values (Setup › Exercises, phase start and chat lists still read it).
- Writes: `progression.classify` / `set_paused` (every chat tool and web command goes through them) add a row valid from `now`'s date.
- Deviation: an exercise's **first** classification (none in force on any day before) is written into its whole history instead of from today. It describes the exercise rather than changing it; otherwise the model's phase-start classification would make every excluded lift count on all earlier weeks. Later flips are dated.
- Readers: `progression.lifts(coach, until)` gives the lift's `counts` / `paused` as of `until`, each entry `paused` as on its session's day, and `setting_changes` for `progression.counts_on(lift, day)`. `progression.week` takes counts and the paused status as of the week's last day and drops PRs set while paused. `strength_trend.compute` includes a lift in each point by its classification on that point's day. `session` view, web lift (PR marks, pause reason as of the day) and Home's PRs per session use the session day's pause. New `progression.setting_on(coach, exercise_id, day)`.
- `test_lift_progression.py::test_two_lifts_declining…`: the pause made on 30 Nov now shows from the week ending 30 Nov (was read for the week ending 29 Nov).
