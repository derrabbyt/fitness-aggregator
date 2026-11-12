# 05: Cut phase

**What to build:** Phase start accepts `cut`: `cut_level` (conservative 500 / moderate 750 default / aggressive 1000 with a warning) or `goal` {weight_kg|body_fat_pct, date} -> rate and deficit (cap 1000, warn past moderate, suggest the level); optional `end_date` (mini-cut). Start kcal = maintenance estimate - deficit (preview, confirm/change). Target rate = deficit x 7 / 7500; band = target x (1 +- 0.4). Weekly: on target -> hold; stalled + adherence -> 100-200 kcal less (carbs first; steps offered in text); stalled without adherence -> no change; too fast -> +100. Macros 2.5 g/kg protein, 0.6 g/kg fat floor. Week 1 not judged, no glycogen window. Reaching end_date asks to end the phase.

**Blocked by:** follow-ups 01, follow-ups 03, follow-ups 05

**Status:** ready-for-agent

- [ ] Skill `phase-cut` params + schema finalized; validator green
- [ ] Tests: start from level and from goal (cap, warning), band, the four weekly cases, macros, end_date
- [ ] Phase start preview shows level, deficit, rate, band
- [ ] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.
