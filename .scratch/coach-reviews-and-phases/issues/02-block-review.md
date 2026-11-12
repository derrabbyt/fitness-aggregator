# 02: Block review

**What to build:** Setup value `block_weeks` (default 5, with history). Block n ends at phase start + n x block_weeks; chat tool `end_block(reason)` ends the current block today and restarts the count. Facts in code: strength trend and per-lift statuses over the block, stalls, deload signal, sessions done vs planned, session volume (> 20 sets/session, > 4 sets/muscle/session; muscle from Hevy template when known). Skill `block-review` writes report + evidence-based advice in words (deload included), never a proposal. Sent and stored once.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Schedule + end_block tests
- [ ] Facts tests (stalls, deload, volume)
- [ ] Skill + schema + example; validator green
- [ ] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.
