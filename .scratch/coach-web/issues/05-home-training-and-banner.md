# 05: Home: training and banner

**What to build:** Home's training block: each of the day's sessions on one line with time of day and duration or distance (lifting from Hevy, Strava runs, planned or skipped wrestling, reported extra sessions), no PRs and no per-exercise detail; below it one trend line ("5 of 7 lifts progressing · 1 stall · 2 PRs this week", without jargon). Tapping opens the Training tab. A banner appears only when a proposal is open (links to the Week page) or a coach question waits in Telegram (says so); only on today.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Read model and schema extended; tests cover a lifting day, a run day, planned / skipped wrestling, an extra session, no sessions, the trend line, banner states (none, open proposal, waiting question), banner absent on past days
- [ ] UI per the design direction; tap → Training tab
- [ ] Build + screenshots in Comments; tests green

## Decisions (user, 2026-11-10, from ticket 01)

Overrides the text above where they differ: two blocks instead of one. **Gym** = lifting sessions (one line each: name, time of day, duration), with the lift trend line under them. **Other activities** = runs (distance, duration, **pace**), wrestling, extra sessions. No "planned" tag anywhere. Tapping either block opens the Training tab.

**Strength trend (user, 2026-11-10; decided by the orchestrator at the user's request):** a 4-week line showing whether lifting is improving overall. For each counting lift, each session's heaviest working set as estimated 1RM (effective load for bodyweight lifts, the same value the lift status uses); per ISO week, each lift's best value as % change from its first session in the 28-day window (after its latest baseline reset, if any); a lift needs ≥ 2 sessions in the window; excluded lifts never count. The plotted value per week is the mean % change over the lifts trained up to that week (each lift carries its last value forward). Shown as a thin line with one number ("+3.2 % in 4 weeks"): green when rising, neutral within ±1 %, red when falling. Computed in code in the coach read model, as of the shown day; core param `training.strength_trend_days: 28` and the ±1 % band reused from `training.e1rm_same_band_pct`. Shown small in the Gym block next to the trend line; tests cover rising, flat, falling, a reset lift, a lift with one session, and a past day.
