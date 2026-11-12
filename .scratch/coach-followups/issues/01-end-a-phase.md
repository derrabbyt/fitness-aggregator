# 01: End a phase from Telegram

**What to build:** The `request_phase_end` chat tool (mode `end`) and `/endphase` send a confirm card; Confirm ends the active phase right away: `status = 'ended'`, `ended_at`, new `end_date` = yesterday (ending on the start day erases the phase instead, said on the card). Open proposals are closed with "phase ended". `phases.on(day)` finds the phase whose span covers a day; `web_week.py` uses it. Weekly check-ins, evening reminders and measurement reminders stop (they already need an active phase). Training feedback runs without an active phase, for sessions first seen after the phase ended (or after deploy when there never was one). MFP goal untouched; the card says so.

**Blocked by:** None

**Status:** ready-for-agent

- [ ] Migration adds `phases.end_date`; `phases.on(day)` helper
- [ ] Tool + command + card + one atomic claim; tests: card, confirm once, proposals withdrawn, jobs stopped, training feedback still sent, ending on the start day
- [ ] coach-chat skill: end on request, never undo unless asked
- [ ] Tests green

Spec: `.scratch/coach-followups/spec.md`.
