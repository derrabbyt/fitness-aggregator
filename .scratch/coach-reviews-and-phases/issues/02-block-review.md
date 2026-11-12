# 02: Block review

**What to build:** Setup value `block_weeks` (default 5, with history). Block n ends at phase start + n x block_weeks; chat tool `end_block(reason)` ends the current block today and restarts the count. Facts in code: strength trend and per-lift statuses over the block, stalls, deload signal, sessions done vs planned, session volume (> 20 sets/session, > 4 sets/muscle/session; muscle from Hevy template when known). Skill `block-review` writes report + evidence-based advice in words (deload included), never a proposal. Sent and stored once.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Schedule + end_block tests
- [x] Facts tests (stalls, deload, volume)
- [x] Skill + schema + example; validator green
- [x] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.

## Comments

Built in `coach/src/fa_coach/features/block_review.py` (tests: `coach/tests/test_block_review.py`).

- **`block_weeks`**: core param `reviews.block_weeks: 5` (replaces the unused range
  `block_length_weeks`), optional setup value `block_weeks` (2-12 in `phase_setup`), merged
  by `phases.params_for`; changed during a phase with `record_setup_value`, so it has
  history (`setup_changes`). The block in progress uses the value in force today.
- **Schedule without a new table**: where a block ended comes from the stored block
  reviews: block n+1 starts the day after the phase's latest block review's
  `period_end` (block 1 on the phase start). The job `block-review` (order 60) reviews a
  block on any tick from the day after its last day; key `"<phase id>:<n>"`.
- **`end_block(reason)`** (chat tool): ends the block today (period_end = today, the next
  block starts tomorrow) and runs the review inside the tool call (nested `coach.ask`), so
  the review goes out before the chat reply. A second `end_block` the same day is refused.
- **Always one review**: without a usable model answer (model error, invalid JSON,
  `send: false`, facts failing the schema) code sends its own short summary, so the block
  boundary is stored and the review isn't retried every tick.
- **Muscle groups** (orchestrator decision, no migration): Hevy workouts carry no muscle
  group, so code gives working sets per session (flag over `volume_note_max_sets_per_session`)
  and per exercise per session with the titles; the skill has the model judge the
  per-muscle note from the titles, worded as an estimate.
- **Sessions vs plan**: done = Hevy sessions in the block; planned = non-optional `lift`
  sessions of the plan in force each day; skipped = lifting sessions reported skipped.
- **Strength trend over the block**: mean of each counting, unpaused lift's e1RM change
  (last vs first session in the block, after a reset in it; needs 2 sessions), flat within
  ±`e1rm_same_band_pct`. Stalls and the deload signal are the lifts' state at the block's end.
- **Words only**: the skill (`decision=True`, no tools) returns `coach_message`; code sends
  only `text`, no buttons, never `propose_change`. To talk about it, the chat gets
  `get_block_review` (text + facts of a sent review); coach-chat has CC-BLOCK.
- Schema `block_facts.schema.json` + example; README, TOOLS.md, coach-chat updated.
- Not done: a web edit of `block_weeks` (not asked; chat only).
