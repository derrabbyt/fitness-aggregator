# 06: Day questions without a phase

**What to build:** `check_recent_days` runs without an active phase: look back `LOOKBACK_DAYS` with no phase-start bound. Without a target the implausible check (2x target) is skipped; the partial check runs as now. Confirmations feed the maintenance estimate's usable weeks as they already do.

**Blocked by:** None

**Status:** resolved

- [x] Tests: partial day asked with no phase; no implausible question without a target; confirmed day makes its week usable
- [x] Tests green

Spec: `.scratch/coach-followups/spec.md`.

## Comments

- `check_recent_days` no longer reads the phase at all: it always looks at the last `LOOKBACK_DAYS` before today. During a phase this also reaches days before its start date (partial check only, since those days have no target), as the spec's "no phase start bound" says.
- No change to `daycheck.py` was needed: without a phase `daily_target` is None, so the implausible check is already skipped and the partial check falls back to the neighbours' median (no target to fall back on when fewer than 3 neighbours are logged).
- Tests in `coach/tests/test_day_confirmation.py`, section "without a phase".
