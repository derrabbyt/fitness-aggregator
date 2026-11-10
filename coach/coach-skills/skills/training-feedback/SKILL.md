---
name: training-feedback
description: Runs once after a logged lifting session has synced. Names PRs and flags a new stall; sends nothing when the session was unremarkable. Code adds the "was this a reset?" question and its buttons. Load with coach-core and the active phase skill. Input daily_facts (kind training); output coach_message.schema.json.
---

# Training feedback

Code has judged every exercise of the session (`session.exercises`). Progress = more load
or reps at the same execution; micro-progressions count (+0.5 kg at the same reps is
improved). Only when load and reps move in opposite directions does code compare
estimated 1RMs (±`training.e1rm_same_band_pct` % = same). For bodyweight exercises (dips,
pull-ups) bodyweight gained counts as load once the trend moved at least
`training.bodyweight_same_load_kg` (smaller changes are the same load): code already
includes it in `top_set.effective_load_kg`, `status` and `is_pr`. Take `status`, `is_pr`, `new_stall` and
`possible_reset` as given; don't re-judge from the sets.

## What to say

- **TF-PR** – Name each exercise with `is_pr`, counting or excluded. Short, factual
  (exercise, load × reps).
- **TF-STALL** – Exercises with `new_stall` (counting exercises only; code never sets it for
  excluded ones): say it once as a flag, keeping the exercise's normal behaviour in mind
  (isolation lifts stall more often). No fix suggestions; no technique cues. `stalled`
  without `new_stall` was flagged before: don't repeat it (the block review does).
- **TF-RESET** – For exercises with `possible_reset`, code appends the question ("technique
  or range-of-motion change, or an exercise swap?") with `mark_reset` / `not_a_reset`
  buttons below your text and sends the message even past the daily limit. Don't ask it
  yourself, don't add buttons, and don't otherwise comment on that drop.
- **TF-SKIP** – Not judged: `new_baseline` (the exercise's first session or the first after
  a reset), `not_judged` (see `not_judged_reason`: after a break, another gym, no working
  set in the rep range) and `paused`. Never call these progress or decline. A new
  baseline is mentioned only in a message you send anyway ("new baseline started");
  it appears only on that first session.
- **TF-CHECK** – If there was a notable drop (not a reset question) or a new stall, add one
  optional line: "anything off today (pump, effort, pain)? – skip if not". If the user
  answers, coach-chat stores it as a context note.

## When to send

- `send: true` only for a PR, a `new_stall` or alongside a reset question. Otherwise
  `send: false`, `text: ""`, and put minor notes (a decline, a steady streak) into
  `deferred_to_weekly`. Code holds back a message sent for anything else.
- The message counts toward the daily limit unless it carries a reset question; past the
  limit code defers it to the weekly report.
- `buttons: []`, `urgent: false` – code decides both.
