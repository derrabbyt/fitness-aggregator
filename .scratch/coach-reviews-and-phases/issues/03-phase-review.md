# 03: Phase review

**What to build:** Every `phase_review_weeks` (10) from phase start and on phase end (follow-ups 01). Facts in code: weight vs band and time goal, strength trend, maintenance estimate, waist trend, body-fat estimates, calibration drift (run discount from Strava vs trend-implied activity; wrestling likewise). Drift beyond a threshold makes calibration proposals through the existing path. Skill `phase-review` writes it; after a phase end it asks what comes next.

**Blocked by:** 01, 04, follow-ups 01, follow-ups 03

**Status:** ready-for-agent

- [ ] Schedule (10 weeks, on end) tests
- [ ] Calibration drift -> proposal test
- [ ] Skill + schema; validator green
- [ ] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.
