---
name: block-review
description: Runs at the end of each training block (every reviews.block_weeks weeks from the phase start, counted again after the user ends a block with end_block). Reports lift trends, stalls, fatigue and deload signals, sessions done vs planned and a session-volume note, then gives evidence-based advice in words (a deload week included when the signals point there). Never a proposal. Load with coach-core and the active phase skill. Input block_facts.schema.json; output coach_message.schema.json.
---

# Block review

Input: `block_facts` (code computed every number). Take statuses, streaks, `change_pct`,
`stalls`, `declining_lifts`, `deload_signal` and `over_limit` as given; don't re-judge from
the sets (CORE-NO-MATH). `block.ended_early` with `block.reason`: the user ended the block
("block done"); mention it in one line.

## Report

1. **BR-LIFTS** – The strength trend over the block (`training.strength_trend`), then the
   lifts grouped: improving, holding, declining (from `statuses`, `change_pct` and the
   streaks at the end). Name PRs. Don't list every session. Excluded lifts
   (`counts: false`) only for a PR; paused lifts only as paused.
2. **BR-STALLS** – Each lift in `training.stalls`, once, with the exercise's normal
   behaviour in mind (isolation lifts and small muscles stall more often).
3. **BR-FATIGUE** – `training.deload_signal` and `declining_lifts`, sport-load or illness
   notes (`context_notes`), missed sessions (`sessions.done` against `sessions.planned`,
   `sessions.skipped`). Say whether the signals cluster or are explained by context.
4. **BR-VOLUME** – A note only when a session is `over_limit` (more than
   `volume.max_sets_per_session` working sets). Per muscle: Hevy sends no muscle groups,
   so judge from the exercise titles whether one muscle got more than
   `volume.max_sets_per_muscle_per_session` working sets in a session (e.g. two pressing
   movements for chest), and word it as your estimate ("looks like about … sets for
   chest"). A note, not a rule. Nothing when nothing stands out.
5. **BR-RESETS** – Baseline resets (`baseline_resets`) and paused lifts, so the user sees
   why some lifts have short histories.

## Advice (food for thought)

6. **BR-ADVICE** – Two to four short points of evidence-based advice in words, tied to the
   facts above. Examples of what fits:
   - several lifts declining, or fatigue signals clustering → consider a deload week
     (lower load or fewer sets for about a week, then resume);
   - a lift stalled while the rest progress → options such as a different rep range, a
     variation, or more rest before it; note that staying the same can be fine in a cut;
   - long sessions over the limit → splitting volume across sessions, since output drops
     late in long sessions;
   - many missed sessions → consistency before changing the program.
   Present them as options to think about, with the reason; the user decides. No technique
   cues, no full programs, no numbers that aren't in the facts or `params`.
7. **BR-NEXT** – One line on what to watch in the next block ("if bench still stalls after
   the next block, it may need a look").

## Rules

- Words only: never call `propose_change`, never offer a change for approval, no buttons
  (CORE-AUTHORITY). The user can talk about it in the chat.
- Keep it to training; nutrition belongs in the weekly report.
- `send: true`, `buttons: []`, `deferred_to_weekly: []`. Telegram-ready, compact: short
  headings or bullets, well under a screen and a half.
