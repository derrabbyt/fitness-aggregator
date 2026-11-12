# 02: Undo (erase) a phase on explicit request

**What to build:** `request_phase_end` with mode `undo`, only when the user's message explicitly asks to erase or undo a phase (skill + tool description). The card lists what is deleted (the phase, its setup, targets, proposals, weekly verdicts and reports, day questions and confirmations from its days); Confirm deletes them in one transaction. MFP goal untouched. Works on the active phase and on the latest ended one.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Delete in one transaction; other phases untouched (test)
- [x] Card lists the counts of what goes
- [ ] Tests green

Spec: `.scratch/coach-followups/spec.md`.

## Comments

- **No migration.** `phase_end_requests.mode` has no CHECK, so `undo` fits; an undo card always has `effect = 'erase'`.
- **Target:** `phase_end.target(coach, mode)`: `end` → the active phase; `undo` → `phases.latest` (the active one, else the most recently started ended one). A tap re-checks that the card's phase is still the target (e.g. a new phase started since → "out of date", nothing changes).
- **Erase is table-driven:** `_erase_parts(coach, phase, today)` lists (kind, `FROM … WHERE …`, params) in delete order; `erase` deletes and `erase_counts` counts with the same rows. Ticket 03: add a `setup_changes` row there (before `phases`), and a `LABELS` entry only if the card should show it.
- **Card:** "Erase the phase “…” (Mon 9 Nov – today / – Thu 19 Nov, ended)?", then the phase and its setup and a count line per labelled kind (targets, proposals, weekly verdicts and reports, day questions, day confirmations; zero counts shown), what is kept, "no target from today…" only for the active phase, the MFP goal line, "This can't be undone." The outcome edit repeats the actual counts.
- **Open proposals' cards** (report and proposal messages) are edited "⏹ Phase erased. Nothing changed from this proposal." on any erase (undo or start-day end). Their texts are read before the delete via the new `proposals.card_edits` (`close_cards` uses it).
- **No command for undo:** only the chat tool, as the spec says; `/endphase` stays end-only.
- **End card (ticket 06 merged):** now says training feedback and day questions keep running.
- **Skills:** coach-chat CC-PHASE-UNDO; TOOLS.md row covers `undo`.
- **Atomicity test** makes the `DELETE FROM phases` fail and checks every table is unchanged and the card still open (monkeypatching `db.execute`: the only way to force a mid-transaction failure through the seam).
