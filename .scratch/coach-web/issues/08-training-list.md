# 08: Training: list

**What to build:** The Training tab lists every lift alphabetically with its status (progressing, same, declining, stall, paused, new baseline) and a small chart, without grouping by session type; lifts that don't count sit in a collapsed "Not counted" section. Below, a recent list of runs and other sessions (wrestling, extra sessions) with date, type, km or minutes and kcal counted.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Coach-core read model `training()` with schema; tests cover counting and excluded lifts, each status, a bodyweight lift (effective load), runs and other sessions
- [ ] UI list and sections; build + screenshots in Comments; tests green
