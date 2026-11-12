# 01: Reviews table and their place on the web

**What to build:** Migration `reviews (id, kind block|phase|photo, phase_row_id, period_start, period_end, facts JSON, text, created_at)`; once-keyed send helper; the Week read model lists reviews sent in the week (collapsed like the report); Setup › Measurements lists body-fat estimates (table `body_fat_estimates (date, pct, source model|user, review_id)`).

**Blocked by:** None

**Status:** ready-for-agent

- [ ] Migration + schemas + examples
- [ ] Week view and Setup measurements show them (tests)
- [ ] Web UI: collapsed review on Week, estimates list
- [ ] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.
