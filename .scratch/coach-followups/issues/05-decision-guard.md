# 05: Weekly change direction and size in code

**What to build:** In `weekly_checkin.py` next to the sport-load hold: from `vs_band` and the distance to the band edge, code computes the expected direction (increase below, decrease above, hold in band) and step (`small_step_kcal` within `far_off_margin_kg_per_week` of the edge, `large_step_kcal` beyond). A proposed change with the wrong direction becomes a hold; with the wrong size gets the expected size; each correction goes into `code_adjustments`; the stored `direction` is code's. Holds and skipped weeks are untouched. Symmetric, so cut/maintenance can reuse it.

**Blocked by:** None

**Status:** ready-for-agent

- [ ] Tests: wrong direction -> hold, wrong size -> corrected, correct verdict unchanged, hold untouched, streak uses code's direction
- [ ] Skill text (weekly-decision / RB-SIZE) notes code enforces it
- [ ] Tests green

Spec: `.scratch/coach-followups/spec.md`.
