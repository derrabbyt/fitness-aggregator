# 04: Training plan in chat

**What to build:** The training plan is seeded once from the CSV export of the user's sheet, kept in the repo's data folder, and from then on lives in the coach's database. In chat the user can see the plan, change it for this week or for good, and report a planned session as skipped or an extra session with its kcal. Counted activity follows the agreed rules.

**Blocked by:** 03 (Context notes and profile in chat)

**Status:** ready-for-agent

- [ ] The current sheet export is moved into the repo's data folder under a stable name and seeds the saved plan on first start (week grid with times, optional runs; exercise lists per session kept for offering tracked lifts)
- [ ] After seeding, the plan changes only through chat; the CSV is not re-read
- [ ] `get_training_plan`, `update_training_plan` (lasting change) and `set_session_status` (this week: skipped, done, or extra with kcal) work from chat and are confirmed in one line
- [ ] Counted activity rules are implemented in code: runs count only when a run synced or the user reported it (synced kcal × run discount); lifting counts when a Hevy session exists that day (fixed kcal per session); wrestling counts as planned unless reported skipped; extra sessions count with the reported kcal
- [ ] `repull_training_plan` is removed from the tools doc and the coach-chat skill; the validator stays green
- [ ] Tests cover seeding, a this-week change, a lasting change, and counted activity for a day with a synced run, a Hevy session, planned wrestling, a skipped wrestling session and an unrun optional run
