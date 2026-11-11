# 08: Training: list

**What to build:** The Training tab lists every lift alphabetically with its status (progressing, same, declining, stall, paused, new baseline) and a small chart, without grouping by session type; lifts that don't count sit in a collapsed "Not counted" section. Below, a recent list of runs and other sessions (wrestling, extra sessions) with date, type, km or minutes and kcal counted.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Coach-core read model `training()` with schema; tests cover counting and excluded lifts, each status, a bodyweight lift (effective load), runs and other sessions
- [ ] UI list and sections; build + screenshots in Comments; tests green

## Decisions

**Strength trend (user, 2026-11-10; decided by the orchestrator at the user's request):** a 4-week line showing whether lifting is improving overall. For each counting lift, each session's heaviest working set as estimated 1RM (effective load for bodyweight lifts, the same value the lift status uses); per ISO week, each lift's best value as % change from its first session in the 28-day window (after its latest baseline reset, if any); a lift needs ≥ 2 sessions in the window; excluded lifts never count. The plotted value per week is the mean % change over the lifts trained up to that week (each lift carries its last value forward). Shown as a thin line with one number ("+3.2 % in 4 weeks"): green when rising, neutral within ±1 %, red when falling. Computed in code in the coach read model, as of the shown day; core param `training.strength_trend_days: 28` and the ±1 % band reused from `training.e1rm_same_band_pct`. Shown larger at the top of the Training tab (same computation, from the read model ticket 05 adds, or added here if 05 is not merged yet; whichever lands second reuses it).

**Strength trend changed by ticket 14 (2026-11-11):** `strength_trend.compute(coach, day, *, days=14, lifts=None)` now returns a daily series, not ISO weeks (schema `web_strength_trend` rewritten): `{window_days, start, end, points: [{date, pct}], rate_pct_per_week, direction, lifts}`. Each day's point is the mean over the counting lifts trained in the 28 days ending that day of the lift's latest e1RM as % of its first one in that window (100 = unchanged; after its latest baseline reset there; a lift trained once is at 100, so the "≥ 2 sessions" rule above is gone). The number is the rate in % per week over the 28 days ((last point − 100) / 4); the ±1 % band now applies to that rate. The web side keeps `StrengthTrendChart` (`ui/strength-trend.ts`, large variant only: rate big, line below) plus `strengthTone` / `strengthRate`; call `compute` with a longer `days` for the Training tab's chart.
