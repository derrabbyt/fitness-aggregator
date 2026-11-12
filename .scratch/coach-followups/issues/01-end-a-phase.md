# 01: End a phase from Telegram

**What to build:** The `request_phase_end` chat tool (mode `end`) and `/endphase` send a confirm card; Confirm ends the active phase right away: `status = 'ended'`, `ended_at`, new `end_date` = yesterday (ending on the start day erases the phase instead, said on the card). Open proposals are closed with "phase ended". `phases.on(day)` finds the phase whose span covers a day; `web_week.py` uses it. Weekly check-ins, evening reminders and measurement reminders stop (they already need an active phase). Training feedback runs without an active phase, for sessions first seen after the phase ended (or after deploy when there never was one). MFP goal untouched; the card says so.

**Blocked by:** None

**Status:** resolved

- [x] Migration adds `phases.end_date`; `phases.on(day)` helper
- [x] Tool + command + card + one atomic claim; tests: card, confirm once, proposals withdrawn, jobs stopped, training feedback still sent, ending on the start day
- [x] coach-chat skill: end on request, never undo unless asked
- [x] Tests green

Spec: `.scratch/coach-followups/spec.md`.

## Comments

- **Migration `22_phase_end.sql`:** `phases.end_date` (NULL while active), seeded for already-ended phases as the day before `ended_at` (a phase replaced on its start day gets an empty span). Table `phase_end_requests` holds the cards: `mode` (what was asked: `end`; ticket 02 adds `undo`), `effect` (what the card promised: `end` or `erase`), `status` claimed once (`open` → `confirmed` / `cancelled` / `superseded`).
- **`phases.on(coach, day)`:** the phase whose `start_date..end_date` covers the day; the active phase is open-ended (covers future days of the current week too). `_phase` dicts now carry `end_date`. A new phase start (`phase_start.py`) also sets the old phase's `end_date` = yesterday.
- **`web_week.phase_during`** keeps its meaning (a phase covering any day of the week, latest day first) by asking `phases.on` from the week's end back to its start.
- **Card and claim** (`features/phase_end.py`): one conditional UPDATE inside the same transaction as the change. A newer card supersedes older open ones. If on tap the effect would differ from what the card said (start-day card tapped the next day, phase already ended/replaced), nothing changes and the card says it's out of date.
- **Start-day end = erase:** `phase_end.erase(coach, phase, today)` deletes the phase, its `phase_setups` row, targets, proposals (with cards and counter taps), weekly check-ins, and day questions/confirmations from its days; returns counts per table. Written so ticket 02 can reuse it for `undo` (it needs to add the `undo` mode, the counts on the card, and the latest-ended-phase case). Ticket 03 must add `setup_changes` to it.
- **Proposals withdrawn:** status `superseded` (the CHECK constraint has no `withdrawn`), cards edited with "⏹ Phase ended. Nothing changed from this proposal." New `proposals.withdraw_open`; `_close_cards` became public `close_cards`.
- **Training feedback without a phase:** cut-off = latest phase's `ended_at`; with no phase ever, the job's first run (stored as once-key `training-feedback-without-phase-since`), so the backlog synced at deploy gets nothing. `daily_facts.phase_id` / `phase_week` are nullable now (schema + training-feedback skill note).
- **Card wording:** doesn't promise "day questions keep running": they still need an active phase until ticket 06.
- **Not done here:** an ended phase's days showing targets/band on the web needs ticket 03 (`phases.targets` still reads the active phase only), although the card says the phase stays in the history with its targets.
- **Skills:** coach-chat CC-PHASE-END (replaces "End the bulk → phase-review"); TOOLS.md row for `request_phase_end`.
- **Review fixes:** `phases.end_active(coach, at, end_date)` is shared with a new phase start. Without a phase, training feedback's cut-off is the latest of the last `ended_at`, the last confirmed erase (`phase_end.last_erase_at`, the erase card's `decided_at`) and the job's first run without any phase (`db.once_at`), so an erase never lets an old first-run key bring back a backlog.
