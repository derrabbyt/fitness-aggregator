# Coach follow-ups: ending a phase, history for past days, v1 gaps

Status: ready-for-agent

Sources: the questions of 2026-11-12, `.scratch/later/issues/01-coach-reset.md` and `02-setup-value-history.md`, the v1 code review (`.scratch/coach/spec.md`, review finding "step size and direction come only from the model"), `GLOSSARY.md`.

## Problem Statement

- **No way to end a phase.** Undoing the test phase meant stopping the coach and restoring a copy of its database by hand. The only way out of a phase today is starting the next one.
- **Past days use today's values.** The web page shows past days "as of that day", but the setup values (step goal, run discount, wrestling and lifting kcal) and the exercise classification and pause are always today's. A calibration or step-goal change silently rewrites past days, and an ended phase's days lose their targets and band.
- **Four gaps left from v1:**
  - The size and direction of a weekly calorie change come only from the model. Code checks only the maximum.
  - The coach asks "is that all you ate?" only during a phase, so half-logged days before a phase quietly make weeks unusable for the maintenance estimate.
  - The chat can't read my waist history.
  - Phase-start setup can't look things up in MFP or Hevy the way chat can.

## Solution

- **End a phase from Telegram.** I say I want to end the phase (or use `/endphase`). The coach shows a card with what ending means, and nothing happens until I tap confirm.
  - Ending takes effect right away: today already has no target.
  - The phase stays in the history as an ended phase, with its weeks, verdicts and targets visible on the web.
  - Open proposals are withdrawn. Weekly check-ins, evening reminders and waist/photo reminders stop. Training feedback and day questions keep running.
  - The MFP goal is left as it is.
  - Only when I explicitly ask to undo or erase a phase (e.g. "undo it, that was a test") does the card offer to delete the phase and everything that hangs on it, again behind a confirm tap.
- **History for setup values and exercise settings.** Every change to a setup value, an exercise's classification or its pause is stored with the date it takes effect. Every reader looks values up as of the day it computes, so past days stay as they were, including the days of an ended phase.
- **Weekly decision guarded in code.** Code derives the direction (increase below the band, decrease above it, hold in it) and the step size (small within `far_off_margin_kg_per_week` of the band edge, large beyond it) from the week's facts. When the model's verdict disagrees, code corrects it and records the correction, as it already does for the sport-load hold. The streak's directions become code's.
- **Day questions without a phase.** The "is that all you ate?" and "real or a typo?" questions run whether or not a phase is active, so weeks before a phase can count toward the maintenance estimate.
- **Waist history in chat:** a read tool for the model.
- **Live reads in phase start:** phase-start setup gets the same read-only MFP and Hevy tools as chat.

## User Stories

1. As the user, I want to end the active phase by saying so in Telegram or with `/endphase`, so that I don't need someone to restore a database.
2. As the user, I want a confirm card that says what ending changes (no target from today, open proposals withdrawn, check-ins and reminders stop, MFP goal unchanged), so that I know before I tap.
3. As the user, I want ending to take effect right away, so that today shows no target once I've ended the phase.
4. As the user, I want an ended phase to stay visible with its weeks, verdicts and daily targets, so that I can look back at it.
5. As the user, I want to erase a phase completely only when I explicitly ask for that, behind its own confirm card listing what gets deleted, so that a test phase can disappear but a real one never does by accident.
6. As the user, I want my MFP goal left alone when a phase ends or is erased, so that I change it myself.
7. As the user, I want training feedback (PRs, stalls) to continue without an active phase.
8. As the user, I want check-ins, evening reminders and waist/photo reminders to stop without an active phase.
9. As the user, I want past days to use the setup values that were in force that day, so that a calibration or step-goal change doesn't rewrite history.
10. As the user, I want past days to use the exercise classification and pause in force that day, so that flipping a lift doesn't change old weeks.
11. As the user, I want an ended phase's days to keep their targets and band on the web.
12. As the user, I want the weekly change's direction and size to follow the band rules even when the model gets them wrong, with the correction noted in the verdict.
13. As the user, I want to be asked about suspicious days even without a phase, so that my clean-tracking weeks before the reverse count.
14. As the user, I want to ask the coach about my waist history in chat.
15. As the user, I want the coach to look things up in MFP and Hevy while setting up a phase.

## Implementation Decisions

- **Ending a phase** (`features/phase_end.py`, new):
  - **Trigger:** a chat tool `request_phase_end(mode: "end" | "undo", reason)`, used when I ask, plus the `/endphase` command. `mode: "undo"` only when I explicitly ask to erase or undo (the skill says so). Both send a card; the tool itself changes nothing.
  - **The card:** `end` lists the effects. `undo` lists what will be deleted: the phase, its setup, targets, proposals, weekly verdicts and reports. Day questions and confirmations stay: they belong to the days, not the phase (they run without a phase). Buttons are Confirm and Cancel. One atomic claim per card, as for proposals.
  - **End:** the phase gets `status = 'ended'`, `ended_at`, and a new `end_date` (its last day = yesterday; a phase ended on its start day is erased by the same rule as undo, after saying so on the card). Open proposals are closed with "phase ended", cards edited.
  - **Undo:** deletes the rows above in one transaction.
  - **MFP goal:** untouched in both cases. The card says so.
  - **Phase span:** readers use `start_date..end_date` (or today while active) to find the phase of a day (`phases.on(day)`). `web_week.py` already looks up "the phase whose span covers the week"; it switches to that helper.
- **Jobs without an active phase:**
  - **Stop:** weekly check-in, evening reminder/recap and measurement reminders. They already return without an active phase.
  - **Keep running:**
    - **Training feedback:** for sessions first seen after the phase ended, or after this change ships when there was never a phase, so no backlog flood.
    - **Day questions:** see below.
- **Setup value history** (migration `22_setup_history.sql`):
  - A table `setup_changes (phase_row_id, key, value JSON, valid_from, source, ref, created_at)`, seeded from each phase's `setup` at its start date.
  - The `phases.setup` JSON stays as the latest values. `phases.params_on(coach, day)` merges the setup values in force that day for the phase of that day; `params(coach)` stays as today's.
  - Every computation for a specific day goes through `params_on`: daily target, steps kcal, session kcal, the Home and Week read models, and the weekly facts.
- **Exercise settings history:**
  - `exercise_setting_changes (exercise_id, classification, paused, paused_reason, valid_from, created_at)`, seeded from `exercise_settings` with `valid_from = '0001-01-01'`.
  - `progression.lifts(coach, day)` and the strength trend use the setting in force on each session's day for judging, and on the day shown for "counts".
  - Changes take effect the day they're made.
- **Weekly decision guard** (`weekly_checkin.py`, next to the sport-load hold):
  - From `vs_band` and the distance to the band edge, code computes the expected direction and step size (`small_step_kcal` / `large_step_kcal`).
  - **When the verdict proposes a change**, code checks the direction and the size against the expected ones. A wrong direction becomes a hold. A wrong size becomes the expected size. Each correction is added to `code_adjustments`, and the stored `direction` is code's.
  - **When the model holds, or the week is skipped,** the verdict stays unchanged (no proposal is forced). For a week that counts, the stored `direction` is still code's expected direction, so a hold below the band counts toward the increase streak.
  - The rule lives in the reverse-bulk params (RB-SIZE) and stays symmetric, so the cut and maintenance phases can reuse it later.
- **Day questions without a phase:** `check_recent_days` drops the phase requirement. The look-back is the last `LOOKBACK_DAYS` with no phase start bound. Without a target, the "implausible" check (2× the target) is skipped; the "partial" check (under half the usual intake) already needs no target.
- **Waist history tool:** a model tool `waist_history(limit)` returning dated values, the phase start value included, in coach-chat's tool list.
- **Live reads in phase start:** the phase-start task gets the `live` tool source (the read-only `READ_TOOLS` allowlist, unchanged). The phase-start skill says that live reads are for looking things up and setup values still go through its own tools.

## Testing Decisions

- Through the Coach seam with the fakes, as before:
  - ending (card, confirm, effects, the claim applying once, proposals withdrawn, jobs stopped, training feedback still sent);
  - undo (rows gone, other phases untouched);
  - ending on the start day;
  - past-day targets after a calibration change and after a step-goal change;
  - an ended phase's day still showing its target and band;
  - a lift excluded later still counted on earlier weeks;
  - the decision guard (wrong direction → hold, wrong size → corrected, a correct verdict unchanged, a hold untouched);
  - day questions with no phase;
  - the waist tool;
  - live tools offered in phase start.
- Migrations seeded from existing data (a test DB with a phase and settings before the migration).
- `docker compose run --rm test` green; the skills validator green.

## Out of Scope

- Resetting non-phase coach data (profile, notes, exercise classification, measurements, photos).
- Restoring the MFP goal on end or undo.
- A web button for ending a phase (approvals and phase changes stay in Telegram).
- Block, phase and photo reviews; cut and maintenance phases; replay tests (next, separately).

## Further Notes

- "End only unless I say otherwise": `undo` must never be the model's default. The coach-chat skill and the tool's description say to use it only when my message asks to erase or undo a phase; the undo card (listing what gets deleted) is the real guard.
- Training feedback without any phase yet is my reading of "keep training feedback without an active phase". It starts with sessions first seen after deploy.
