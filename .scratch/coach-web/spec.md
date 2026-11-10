# Coach web page

Status: ready-for-agent

Sources: the grilling session of 2026-11-10, `.scratch/coach/spec.md` ("Out of Scope": the coach page), ADR 0001, `GLOSSARY.md`, and the Sure design-language reference (`docs/design/sure-reference.md`).

## Problem Statement

The coach runs in Telegram and the web UI is one plain page of MyFitnessPal and Hevy data for a day. To see where I stand, I have to piece it together: my calories against the coach's daily target, today's weigh-in against the trend, steps against the step goal, what I trained, how I slept, whether my lifts are progressing, and what the coach decided this week. The coach's data (targets, weekly decisions, lift progression, the training plan, context notes, setup values) is only reachable by asking in chat. Changing the plan or a setup value means a chat conversation even when I know exactly what I want. I want one calm, phone-first page that shows what matters at a glance, lets me drill into the week and my training, and lets me edit the coach's setup directly. Decisions about calories stay in Telegram.

## Solution

A coach section in the existing web UI, phone first and fine on desktop, in a calm design language modelled on Sure (sure.am): cards with hairline outlines, big numbers, thin charts, and colour only where something is on or off target. Bottom tabs: **Home · Week · Training · Setup**.

**Home** shows one day (today by default; arrows and a date picker for past days, every value as it stood that day):
- food in the usual food-app style (kcal eaten vs the coach's daily target and kcal left, plus protein, carbs, fat and fiber vs targets);
- today's weigh-in, with the 7-day trend, the weekly rate against the target band and a 14-day line;
- steps against the step goal with the kcal ± so far;
- the day's training sessions, one line each;
- a one-line training trend;
- last night's sleep.

A banner appears only when a proposal or a question is waiting, and a warning line only when the data is stale.

**Week** shows the check-in week: the decision first, in plain words, with any open proposal (show only; I approve it in Telegram), then weight, intake, training and notes and flags. The full report sits collapsed at the bottom.

**Training** lists every lift alphabetically with its status and a small chart. Lifts that don't count sit in a collapsed section. Runs and other sessions follow in a recent list. A lift opens to its history chart, its last sessions and its controls.

**Setup** lists the coach's setup in sections, each opening to view and edit with the same rules as chat. A change to an activity value becomes a proposal I approve in Telegram.

The page reads the coach's stored data and opens instantly. A refresh button syncs MFP and Hevy on demand. The old day view stays reachable under `/legacy`.

## User Stories

### Access and navigation

1. As the user, I want the coach page to open on my phone as the web UI's start page, so that it's the first thing I see.
2. As the user, I want bottom tabs Home, Week, Training and Setup, so that every part is one tap away with my thumb.
3. As the user, I want the layout to work on desktop too, wider but with the same content, so that I can use it at a computer.
4. As the user, I want the page reachable only inside my tailnet, with no login, so that it's private without extra steps.
5. As the user, I want the old day view kept under `/legacy`, reachable by URL only and never linked from the UI, so that nothing I relied on disappears and the UI stays clean.
6. As the user, I want the page to follow my phone's light or dark theme, so that it's comfortable at night.
7. As the user, I want the page to open instantly from the coach's stored data, so that I don't wait for MFP.
8. As the user, I want a refresh control that syncs MFP and Hevy now and then reloads, so that I can see food I just logged.
9. As the user, I want one warning line only when the data is older than the stale limit, and nothing otherwise, so that I'm not distracted.
10. As the user, I want no explanatory clutter (for example "estimated from phone use"), so that only what matters is on screen.

### Home: the day

11. As the user, I want Home to show today by default, so that the common case needs no taps.
12. As the user, I want arrows and a date picker to show any past day the same way, so that I can look back.
13. As the user, I want every value on a past day as it stood that day (its trend, its rate, its target, its lift trend), so that history isn't rewritten by later data.
14. As the user, I want the blocks in the order food, weight, steps, training, sleep, so that what I act on during the day comes first.
15. As the user, I want a banner only when a proposal is open or a coach question waits in Telegram, so that I notice what needs me and see nothing otherwise.
16. As the user, I want the banner to take me to the proposal on the Week page, or to say the question waits in Telegram, so that I know where to act.

### Home: food

17. As the user, I want kcal eaten against the coach's daily target, with kcal left shown big, so that I know at a glance what I can still eat.
18. As the user, I want protein, carbs, fat and fiber against their targets shown directly, the way food-tracking apps show macros, so that I need no tap for them.
19. As the user, I want the coach's daily target (base at the step goal, steps, counted sessions, surplus), never MFP's goal, so that there's one source of targets.
20. As the user, I want food without a target before a phase is active, so that the page works before I start the reverse.
21. As the user, I want to tap food to see the check-in week so far (each day eaten against target), so that I can see how the week is going.

### Home: weight

22. As the user, I want today's weigh-in as the main number and the 7-day trend as the second, so that I see both the scale and what it means.
23. As the user, I want the weekly rate coloured against my target band (on target, under, over), so that I see whether I'm gaining as planned.
24. As the user, I want a small 14-day line of the trend, so that I see the direction.
25. As the user, I want to tap weight to see a longer chart (4 or 12 weeks) with the target band shaded, so that I see the bigger picture.
26. As the user, I want a list of recent weigh-ins with outliers marked, so that I can spot typos.
27. As the user, I want my waist values in the weight detail, so that body changes sit next to weight.
28. As the user, I want this week's predicted weight against the actual one, so that I see whether the plan behaves as expected.

### Home: steps

29. As the user, I want a progress bar of steps against the step goal with the steps still to go, so that I know how far I am.
30. As the user, I want the kcal added or taken off so far shown small next to it, so that I know where I land.
31. As the user, I want a day without tracked steps (under the not-tracked limit) shown as not tracked, not as a big deficit, so that a forgotten phone doesn't look like a problem.
32. As the user, I want to tap steps to see the last 14 days against the goal, so that I see my pattern.

### Home: training

33. As the user, I want each of the day's sessions on one line with its time of day and duration or distance ("Push · 06:50 · 66 min", "Run · 17:25 · 11.5 km"), so that I see what I did without exercise detail.
34. As the user, I want planned wrestling shown as planned until I skip it, so that the line matches how it's counted.
35. As the user, I want one trend line ("5 of 7 lifts progressing · 1 stall · 2 PRs this week") without jargon like "counting lifts", so that I know if training is moving.
36. As the user, I want to tap training to open the Training tab, so that detail lives in one place.

### Home: sleep

37. As the user, I want last night's sleep as hours asleep and from–to ("7 h 36 · 23:10–06:46"), so that I see how I slept.
38. As the user, I want "–" when there's no sleep data, so that a missing night isn't an error.
39. As the user, I want to tap sleep to see the last 14 nights, so that I see my pattern.

### Week

40. As the user, I want the Week page to show the check-in week (the 7 days the coach judges), with the current week in progress by default, so that it matches the coach's decisions.
41. As the user, I want arrows to move to older weeks, so that I can review past decisions.
42. As the user, I want the week's decision first, in plain words (hold, +100, −200, and why), so that I know what happens next.
43. As the user, I want an open proposal shown with its reasoning, guardrail status and when it would apply, so that I can decide in Telegram knowing the details.
44. As the user, I want no approve, reject or counter on the web, so that decisions and discussions stay in the coach chat.
45. As the user, I want a weight block with the trend against the target band, the weekly rate and the weigh-in count, so that I see the week's weight picture.
46. As the user, I want an intake block with each day eaten against target, the weekly average, the adherence result and macros against targets, so that I see whether the week counts.
47. As the user, I want a training block with lifts progressing, stalls, PRs, sessions done against planned, and steps per day, so that I see the training side.
48. As the user, I want a notes and flags block with the week's context notes, the flags (protein, fiber, …), deferred items and what's due next week, so that nothing gets lost.
49. As the user, I want unusable or skipped weeks explained in one line, so that I know why a week didn't count.
50. As the user, I want the coach's full weekly report collapsed at the bottom, so that I can read it without it crowding the page.
51. As the user, I want a week in progress to show what's known so far, without a decision yet, so that I can follow it during the week.

### Training

52. As the user, I want all lifts listed alphabetically, each with its status (progressing, same, declining, stall, paused, new baseline) and a small chart, so that I can scan them quickly.
53. As the user, I want lifts that don't count for the decision in a collapsed "Not counted" section, so that the main list shows what matters.
54. As the user, I want no grouping by session type, because sessions can be anything (full body, powerlifting, other), so that the list stays about the lift.
55. As the user, I want to tap a lift to see its history chart (heaviest working set as estimated 1RM, PRs and baseline resets marked), so that I see its progress over time.
56. As the user, I want pull-ups and dips charted on the effective load (bodyweight plus added weight) like any other lift, so that there's one consistent view.
57. As the user, I want the lift's last 3 sessions, one line each (date, heaviest working set, status), with "show more", so that I get context without Hevy-level detail.
58. As the user, I want controls on a lift to switch counts / not counted, pause or unpause it, and mark a baseline reset with a reason, so that I can manage it without chat.
59. As the user, I want a recent list of runs and other sessions (wrestling, extra sessions) with date, type, km or minutes and kcal counted, so that activity has its place.

### Setup

60. As the user, I want Setup as a list of sections, each with a one-line summary, so that I see my setup at a glance.
61. As the user, I want a Phase & targets section with the active phase, phase week, base maintenance, surplus, step goal and current daily targets, so that I see what drives my numbers.
62. As the user, I want to change the step goal directly, so that I can adjust it without chat.
63. As the user, I want an Activity values section (run discount, wrestling kcal, lifting kcal per session) where a change becomes a proposal I approve in Telegram, so that calibration stays deliberate.
64. As the user, I want a Messaging section (check-in day and time, evening reminder time, daily message limit, step-floor window) that saves directly, so that I control when the coach writes.
65. As the user, I want a Training plan section to view the week and change it for good or for this week (skip, done, extra session), so that the plan follows my life.
66. As the user, I want an Exercises section listing every exercise as counting or not counted, with a toggle, so that I can fix the coach's classification.
67. As the user, I want a Context notes section to see, add and delete notes with dates and tags, so that the coach's context is visible and editable.
68. As the user, I want a Profile section to view and edit my coach profile, so that I control what it knows about me.
69. As the user, I want a Measurements section with waist values (and adding one) and my photo sets by date, so that measurements are in one place.
70. As the user, I want every edit validated exactly as in chat, and a clear one-line error when a value is rejected, so that the web can't put the coach in a bad state.
71. As the user, I want each saved change confirmed in place and visible in Telegram-side behaviour right away, so that both stay in sync.
72. As the user, I want starting a phase to stay in Telegram, so that the guided setup keeps working as it does.
73. As the user, I want confirming partial or implausible days to stay in Telegram, so that there's one place for those questions.

### Safety

74. As the user, I want the web never to write to MyFitnessPal, so that only the coach's approved changes touch MFP.
75. As the user, I want targets, the phase and the MFP goal to change only through proposals approved in Telegram, so that the web can't change calories.
76. As the user, I want the coach to stay the only process that opens its database, so that data stays consistent.

## Implementation Decisions

### Architecture (ADR 0001)

- **Coach HTTP API.** The coach service gets a small HTTP server in its own process and event loop, next to the Telegram polling and the scheduler. It isn't published on the host; only `fa-api` reaches it over the compose network.
- **`fa-api` passes it through.** Requests under `/api/coach/` go to the coach unchanged. Access control is the tailnet (`FA_BIND`), with no login. `fa-api` adds nothing coach-specific.
- **Sleep stays with `fa-api`.** The phone sleep estimate is `fa-api` data (`/api/sleep`), so the frontend reads it from there, not from the coach.
- **One process owns the coach's database.** The coach HTTP server is part of the coach process, which stays the only one that opens it.

### Coach core: read models and commands (the test seam)

- **New Coach-core read models, one per page, all JSON:**
  - `home(day)`: food against the daily target and macro targets; weight (weigh-in, 7-day trend, weekly rate, band, 14-day series); steps (steps, goal, kcal so far, tracked or not); the day's sessions; the training trend line data; banner state; freshness.
  - `home_detail(day, block)`: week so far, the longer weight series with weigh-ins, outliers, waist and prediction, and 14 days of steps.
  - `week(iso_week)`: the stored check-in (decision, facts, verdict, report) or the facts so far for the week in progress, with open proposals shown read-only.
  - `training()` and `lift(exercise_id)`: status, series for the charts, sessions with "show more" paging, and controls state.
  - `setup()` and one view per Setup section.
- **"As of that day."** Every read model takes the day and computes values from stored data as of that day: targets valid that day, the trend ending that day, the lift trend over the 2 weeks ending that day. Nothing extra is stored.
- **Web edit commands go through the same code paths as the chat tools.** That covers setup values, step goal, messaging, training plan (lasting change and this-week session status), context notes (add and delete), profile, exercise classification, pause, baseline reset, adding a waist value, and calibration changes (which create a `calibration_change` proposal).
  - Validation is shared with chat.
  - A rejected value returns the same plain reason chat would give.
  - Edits that chat records without a tap are recorded the same way from the web.
- **Not exposed as web commands:** approving, rejecting or countering proposals, starting or confirming a phase, confirming days, writing the MFP goal, and any MFP or Hevy write.
- **Refresh** runs the coach's sync and then returns the requested read model.
- **The API contract** is a JSON schema per read model, kept next to the coach-skills schemas. Read models validate against it in tests.

### Frontend

- **Same Angular app.** Routes for the four tabs plus detail views. The current day view moves under `/legacy` unchanged.
- **Design language** modelled on Sure, not copied:
  - CSS custom properties for light and dark tokens, following the phone's theme;
  - Geist-style type in two weights, 30px big numbers, quiet small uppercase labels, tabular figures;
  - cards with 12px radius and a hairline ring instead of a border;
  - thin progress bars;
  - thin line charts drawn as hand-written SVG (no chart library), without axes clutter;
  - colour only for on or off target.
  The reference is `docs/design/sure-reference.md`. No Sure logo, name or assets.
- **Food block** in the common food-tracking style: kcal eaten / target with "left" big (a ring or a bar), and macro and fiber bars against targets.
- **Phone first:** the bottom tab bar respects the safe area. On desktop the content is centred at a readable width, and wider sections may use two columns.
- **No build-time dependency on the coach being up.** API errors show an inline empty or error state.

### Delivery

- **First release:** Home and its detail views (the landing page the user cares about most), then Week, Training and Setup.
- **Design process:**
  - a throwaway Home prototype at phone width for the user to react to, before Home is built;
  - a design pass with the impeccable skill during the build;
  - a design review of the finished pages against the Sure-style direction.

## Testing Decisions

- **One seam: the Coach core,** as in v1. Tests drive the core with the existing fakes (api client, model client, clock, outbox) and call the new read models and edit commands. Assertions cover observable behaviour only:
  - the read models' JSON, valid against the schemas and with the right numbers for the day and week, including past days "as of that day";
  - stored state after edits;
  - proposals created by calibration edits;
  - rejected edits with their reasons.
  No asserting on SQL or internal helpers.
- **Covered through the seam:**
  - Home for today, a past day and a day before any phase;
  - weight rate against the band;
  - steps tracked and not tracked;
  - sessions on one line each;
  - the training trend line;
  - banner state (open proposal, waiting day question);
  - freshness and stale;
  - Week for a finished check-in, a week in progress and an unusable week;
  - Training list and lift detail, including bodyweight lifts, excluded lifts and paging;
  - every Setup edit, with each rejection path, and calibration becoming a proposal.
- **Prior art:** the v1 coach tests (`coach/tests`), especially the weekly check-in, lift progression, steps, `/today` and plan-chat tests, and the fakes in the coach test package.
- **Not unit-tested:** the coach HTTP adapter and the `fa-api` pass-through, which are thin and checked once by hand, as v1's api endpoints were. The Angular UI has no unit tests: it's checked by a production build plus screenshots at phone and desktop width against fixture data that matches the schemas, reviewed by a design agent.
- **Run:** `docker compose run --rm test` stays green with no network, food bot tests and skills validator included.

## Out of Scope

- Approving, rejecting or countering proposals on the web (they stay in Telegram).
- Starting or confirming a phase on the web, and confirming partial or implausible days on the web.
- Any write to MyFitnessPal or Hevy from the web.
- Login or passwords (tailnet only).
- Per-exercise Hevy-level detail (every set of every session).
- Photo review, block review and phase review (still after v1), and the small v1 gaps (waist history in chat, confirmation streak direction in code, live reads in phase start, asking about partial days before the phase).
- Push notifications or offline support.

## Further Notes

- The Home page is the priority. If the release has to be cut, Home with its detail views ships first.
- The weekly report text is the one the coach sent to Telegram; the Week page is built from the stored facts and verdict, not from that text.
- Sleep comes from the phone-ping proof of concept in `fa-api`. If that changes, only the frontend's sleep block is affected.
