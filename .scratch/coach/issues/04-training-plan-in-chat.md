# 04: Training plan in chat

**What to build:** The training plan is seeded once from the CSV export of the user's sheet, kept in the repo's data folder, and from then on lives in the coach's database. In chat the user can see the plan, change it for this week or for good, and report a planned session as skipped or an extra session with its kcal. Counted activity follows the agreed rules.

**Blocked by:** 03 (Context notes and profile in chat)

**Status:** resolved

- [x] The current sheet export is moved into the repo's data folder under a stable name and seeds the saved plan on first start (week grid with times, optional runs; exercise lists per session kept for offering tracked lifts)
- [x] After seeding, the plan changes only through chat; the CSV is not re-read
- [x] `get_training_plan`, `update_training_plan` (lasting change) and `set_session_status` (this week: skipped, done, or extra with kcal) work from chat and are confirmed in one line
- [x] Counted activity rules are implemented in code: runs count only when a run synced or the user reported it (synced kcal × run discount); lifting counts when a Hevy session exists that day (fixed kcal per session); wrestling counts as planned unless reported skipped; extra sessions count with the reported kcal
- [x] `repull_training_plan` is removed from the tools doc and the coach-chat skill; the validator stays green
- [x] Tests cover seeding, a this-week change, a lasting change, and counted activity for a day with a synced run, a Hevy session, planned wrestling, a skipped wrestling session and an unrun optional run

## Comments

- **Data folder:** `coach/data/training_plan.csv` (the coach's own data; copied into the image and mounted read-only in `test`). Seeded lazily (first `run_due_jobs` or first plan read) when the `training_plan` table is empty; a missing file leaves no plan and is retried, a seeded plan is never re-read.
- **Parsing:** the row starting with "Monday" heads the grid (columns by position, so "Stunday" is fine); filled cells until 3 blank rows are sessions (`06:30 - Pull`, `Mid day: Legs` → `midday`, `opt easy run` → optional "Easy run"); type from the name (run / wrestling / lift / other). The next filled row names the exercise lists: items keep their text, `(X)` = optional, ` / ` and ` and/or ` = alternatives (`KB/Cable` stays one name). Grid "Legs" is not linked to "Legs A"/"Legs B"; the lists are kept separately for offering tracked lifts.
- **Plan versions:** a lasting change stores a new version valid from `from` (default today, not before this Monday), so past days keep the plan they had. Session ids are weekday + position (`fri-1`).
- **`set_session_status`:** `skipped` / `done` / `extra` / `clear`; dates in this or last ISO week (late reports on Monday). Extras need `type` and `kcal`.
- **Counted activity** (`training_plan.counted_activity(day, plan, synced, statuses, params)`, loader `counted_activity_on(coach, day, params)`): returns `{date, kcal, sessions, types}`, sessions in the weekly-facts session shape. Only MFP entries with source `strava` count as runs; HealthKit entries (run copies, "Strength training") never count. Decisions beyond the ticket text, flagged for review: (a) a planned run marked done counts its reported kcal × run discount only when Strava has no run that day; (b) a planned lift marked done with no Hevy session counts the lifting kcal (forgot to log); (c) extra runs are discounted too, other extras count at the reported kcal; (d) a missing setup value raises instead of counting 0.
- **Skills package:** `planned_sessions_default_done` replaced by `activity.lifting_kcal_per_session` (null, setup value) in core params + schema (ticket 05 still adds it to phase setup and the phase-start skill); weekly-facts session status `assumed_done` → `planned`; `training_plan_source` enum is now only `saved_plan`; `repull_training_plan` removed; TOOLS.md, coach-chat (CC-PLAN), context-log and phase-start updated.
