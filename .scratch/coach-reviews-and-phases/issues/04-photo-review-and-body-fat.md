# 04: Photo review and body-fat estimate

**What to build:** After a photo set arrives: the model gets the set and the most recent set at similar leanness (estimate within +-2 %, else the phase start set) as images plus the waist trend, and stores a body-fat estimate (source model). Chat tool `record_body_fat(pct, date)` stores the user's (wins for its date). In a bulk, an estimate >= `bulk.body_fat_advice_pct` (23) sends mini-cut / end-bulk advice, at most once per 4 weeks.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Model client supports image input (fake in tests)
- [ ] Tests: like-for-like pick, user estimate wins, advice threshold and 4-week limit
- [ ] Skill `photo-review`; validator green
- [ ] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.
