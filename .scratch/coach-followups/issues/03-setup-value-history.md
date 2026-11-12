# 03: Setup values as of the day

**What to build:** Migration `setup_changes (phase_row_id, key, value, valid_from, source, ref, created_at)`, seeded from each phase's `setup` at its start date. Every setup change (chat, web, approved calibration) adds a row valid from the day it takes effect; `phases.setup` keeps the latest. `phases.params_on(coach, day)` merges the values in force that day for the phase of that day (`phases.on`); daily target, steps kcal, session kcal, Home/Week read models and weekly facts use it. An ended phase's days keep their targets and band on the web.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Migration with seeding, tested on a DB with an existing phase
- [ ] Tests: past day after a calibration change and after a step-goal change; an ended phase's day shows target and band
- [ ] Tests green

Spec: `.scratch/coach-followups/spec.md`.
