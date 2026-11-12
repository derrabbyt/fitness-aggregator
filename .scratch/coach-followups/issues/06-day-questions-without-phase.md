# 06: Day questions without a phase

**What to build:** `check_recent_days` runs without an active phase: look back `LOOKBACK_DAYS` with no phase-start bound. Without a target the implausible check (2x target) is skipped; the partial check runs as now. Confirmations feed the maintenance estimate's usable weeks as they already do.

**Blocked by:** None

**Status:** ready-for-agent

- [ ] Tests: partial day asked with no phase; no implausible question without a target; confirmed day makes its week usable
- [ ] Tests green

Spec: `.scratch/coach-followups/spec.md`.
