# 02: Setup values with history ("as of that day" for past days)

**What to build:** Not specced yet. Found by the coach-web code review (2026-11-12). The web page shows past days "as of that day", but some inputs always use today's values:
- setup values: step goal, run discount, wrestling kcal and lifting kcal;
- exercise classification and pause;
- the phase, when it has ended.

So a calibration or step-goal change rewrites how past days' targets split into base and activity, the per-session kcal, and the steps still "to go". Past days of an ended phase also lose their target and band. The fix needs setup values (and classification and pause) stored with the date they took effect, and every reader looking them up as of the day.

**Blocked by:** None (to be specced first)

**Status:** resolved

## Comments

- 2026-11-12: specced in `.scratch/coach-followups/spec.md` (tickets 01-04).
