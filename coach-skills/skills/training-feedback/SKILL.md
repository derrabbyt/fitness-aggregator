---
name: training-feedback
description: Runs after a logged lifting session has synced. Reports PRs, stalls and notable drops, and asks whether a big drop was a baseline reset. Sends nothing when the session was unremarkable. Load with coach-core and the active phase skill. Input daily_facts (kind training); output coach_message.schema.json.
---

# Training feedback

Progress = more load or reps at the same execution; micro-progressions count. For
bodyweight exercises (dips, pull-ups) bodyweight gained counts as load – code already
includes it in `effective_load_kg`, `status` and `is_pr`.

## What to say

- **TF-PR** – Name each exercise with `is_pr`. Short, factual.
- **TF-STALL** – For tracked lifts whose `no_progress_streak` reached `training.stall_sessions`,
  say it once as a flag, keeping the exercise's normal behaviour in mind (isolation lifts
  stall more often). No fix suggestions; no technique cues. Repeat in the block review, not
  every session.
- **TF-RESET** – If `possible_reset` is true, ask whether the drop was a technique / ROM
  change or an exercise swap. Buttons `mark_reset` and `not_a_reset` with `ref_id` =
  exercise id. This is the one urgent case (`urgent: true`).
- **TF-SKIP** – Exercises with status `new_baseline` or `paused` are not judged. Mention a new
  baseline only on its first session ("new baseline started").
- **TF-CHECK** – If there was a notable drop (not a reset) or a stall, add one optional line:
  "anything off today (pump, effort, pain)? – skip if not". If the user answers, coach-chat
  stores it as a context note.

## When to send

- `send: false` if there's no PR, no new stall and no reset question; put minor notes into
  `deferred_to_weekly`.
- Respect the daily message limit except for TF-RESET.
