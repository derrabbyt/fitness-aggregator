# 04: Exercise classification and pause as of the day

**What to build:** Migration `exercise_setting_changes (exercise_id, classification, paused, paused_reason, valid_from, created_at)`, seeded from `exercise_settings` with `valid_from = '0001-01-01'`. Changes (chat tools, web) add a row valid from the day made. `progression.lifts(coach, day)` and the strength trend use the setting in force on each session's day for judging, and on the shown day for "counts".

**Blocked by:** None

**Status:** ready-for-agent

- [ ] Migration with seeding
- [ ] Tests: a lift excluded later still counts on earlier weeks; a pause covers only its days
- [ ] Tests green

Spec: `.scratch/coach-followups/spec.md`.
