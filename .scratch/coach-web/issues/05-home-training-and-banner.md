# 05: Home: training and banner

**What to build:** Home's training block: each of the day's sessions on one line with time of day and duration or distance (lifting from Hevy, Strava runs, planned or skipped wrestling, reported extra sessions), no PRs and no per-exercise detail; below it one trend line ("5 of 7 lifts progressing · 1 stall · 2 PRs this week", without jargon). Tapping opens the Training tab. A banner appears only when a proposal is open (links to the Week page) or a coach question waits in Telegram (says so); only on today.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Read model and schema extended; tests cover a lifting day, a run day, planned / skipped wrestling, an extra session, no sessions, the trend line, banner states (none, open proposal, waiting question), banner absent on past days
- [ ] UI per the design direction; tap → Training tab
- [ ] Build + screenshots in Comments; tests green
