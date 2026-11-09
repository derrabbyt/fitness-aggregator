---
name: block-review
description: Runs at the end of each training block (length per reviews.block_length_weeks, from the training plan). Summarises lift trends, stalls, fatigue and deload signals, and session volume. Flags only; the user changes training. Load with coach-core and the active phase skill. Input the block's weekly_facts list plus get_lift_history results; output coach_message.schema.json.
---

# Block review

Input: the `weekly_facts` of every week in the block (code passes them), and
`get_lift_history` for the tracked lifts if you need session detail.

## Content

1. **BR-LIFTS** – For each tracked lift: trend over the block (improving / holding /
   declining), using `status` and streaks from the facts. Group them; don't list every
   session.
2. **BR-STALLS** – Lifts that stalled for `training.stall_sessions` or more, once, with the
   exercise's normal behaviour in mind.
3. **BR-FATIGUE** – Weeks with `training.deload_signal`, sport-load weeks, missed-session
   patterns. If fatigue signals cluster, say "consider a deload" as a flag. Don't prescribe
   the deload.
4. **BR-VOLUME** – A note only if `training.max_sets_in_a_session` exceeded
   `training.volume_note_max_sets_per_session` or `max_sets_per_muscle_in_a_session`
   exceeded `training.volume_note_max_sets_per_muscle_per_session`. It's a note, not a rule.
5. **BR-NEXT** – What to watch in the next block (e.g. "if X still stalls after the next
   block, it may need a look"). No technique cues, no programming prescriptions.
6. **BR-RESETS** – Baseline resets and paused exercises during the block, so the user sees
   why some lifts have short histories.

## Rules

- Flags only (CORE-AUTHORITY); no `propose_change` from this skill.
- Keep it to the training; nutrition belongs in the weekly report.
