# 04: Home: steps and sleep

**What to build:** Home's steps block: a bar of steps vs the step goal with steps to go and the kcal ± so far, and a not-tracked state for days under the not-tracked limit; its detail shows 14 days against the goal. Home's sleep block: last night as hours asleep and from–to ("–" without data), read from `fa-api`'s sleep endpoint; its detail shows 14 nights.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Steps in the coach read model and schema; tests cover above / below goal, not tracked, a run day (run steps removed), a past day
- [ ] Sleep comes from `fa-api` directly in the frontend (it isn't coach data); a missing night or error shows "–"
- [ ] UI blocks and 14-day details; no explanatory notes on the sleep block
- [ ] Build + screenshots in Comments; tests green
