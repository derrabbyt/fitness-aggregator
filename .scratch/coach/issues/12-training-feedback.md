# 12: Training feedback after lifting

**What to build:** When a new lifting session syncs from Hevy, the coach looks at it: PRs are named, a stall on a tracked lift is flagged once, and a sudden big load drop triggers "was this a technique/ROM change or exercise swap?" with buttons. In chat the user can also mark a baseline reset or pause an exercise around an injury.

**Blocked by:** 08 (Lift progression in the weekly decision)

**Status:** ready-for-agent

- [ ] A newly synced lifting session triggers daily facts (kind training) and the training-feedback skill once per session
- [ ] PRs are named; stalls on tracked lifts are flagged the first time only; new baselines are mentioned only on their first session; paused exercises aren't judged
- [ ] A possible reset sends the question with mark-reset / not-a-reset buttons (urgent, exempt from the message limit); mark-reset starts a new baseline from that session; either tap removes the buttons
- [ ] Unremarkable sessions send nothing; minor notes are deferred to the weekly report
- [ ] `mark_baseline_reset` and `set_exercise_paused` work from chat (technique change, ROM change, swap, injury); an injury note leads to an offer to pause, not an automatic pause
- [ ] Tests cover a PR, a first stall flag and no repeat, a reset question with both buttons, a paused exercise, and a silent session

## Decisions (user, 2026-11-09)

Use ticket 08's "Decisions" section: no PR on an exercise's first session; sessions on a day with an `other_location` context note get no PR, no stall flag and no reset question; the reset question compares the heaviest working set (4–20 reps) by estimated 1RM.
