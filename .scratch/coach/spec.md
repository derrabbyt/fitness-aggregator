# Coach v1: reverse-into-bulk loop

Status: ready-for-agent

Sources: `SPEC.md` (scope v0), the coach-skills package, `GLOSSARY.md`, ADRs 0001–0003.

## Problem Statement

I'm coming off a diet and starting a reverse into a lean bulk. Doing it well means watching weight trend, intake, steps and lift progression every week, and changing calories by rule: only when two usable weeks agree, by the right step size, with illness, travel and camps taken into account. Doing that by hand from MyFitnessPal and Hevy is tedious and error-prone, and I either over-react to single days or forget to adjust. The food bot logs food, but nothing watches the whole picture, explains it, or tells me when a change is due. I want a coach that does the watching and the arithmetic, proposes changes, and never changes anything without my OK.

## Solution

A second Telegram bot, the **coach**, running as its own service. It syncs my food, weight, steps and runs from MyFitnessPal and my lifts from Hevy into its own database, computes all numbers in code, and uses Claude (through skills) only to decide and to write. I start a **phase** with a command ("start reverse"); it collects what it needs, shows week-1 targets, and starts on my confirmation. Every week it sends one report with a decision (scenarios A–E) and, when the rules allow, a **proposal** I approve, reject or counter with a tap or a reply. Approved calorie changes update my **daily targets** and set my **MFP goal** to the average daily target. Most days it says nothing; it reminds me in the evening if food, weight or steps are missing, comments only when something is actionable, and reports PRs and stalls after lifting. I can tell it context any time (sick, travel, camp, creatine) and talk to it about my data and plan. It collects waist and photos every two weeks for later review.

## User Stories

### Setup and access

1. As the user, I want the coach to be a separate Telegram bot from the food bot, so that coaching conversations and food logging don't mix.
2. As the user, I want the coach to answer only my Telegram account, so that nobody else can read my data or approve changes.
3. As the user, I want to configure the coach's Claude endpoint, key and models myself, so that I can run it through my own Anthropic-compatible proxy.
4. As the user, I want a cheaper model for chat and daily messages and a stronger one for the weekly decision, so that cost stays low where quality matters less.
5. As the user, I want the coach to run next to the existing services with one `docker compose up`, so that operating it is no different from the food bot.
6. As the user, I want the coach to keep its data in `state/` like everything else, so that moving machines stays "repo + .env + state".

### Data sync

7. As the user, I want the coach to sync food, weight, steps and Strava runs from MyFitnessPal, so that I don't enter anything twice.
8. As the user, I want the coach to sync my lifting sessions (per-set load and reps) from Hevy, so that gym progression is judged on real sets.
9. As the user, I want the first sync to load 16 weeks of history, so that my last diet weeks and starting values can be read from data rather than guessed.
10. As the user, I want the coach to sync several times a day and on demand, so that facts are current when a job runs.
11. As the user, I want the coach to reach MyFitnessPal only through the api, so that the MFP session keeps a single owner and doesn't break.
12. As the user, I want to be told when data is stale (no successful sync within the stale limit), so that I know a week may not count and why.
13. As the user, I want clear weigh-in typos (more than 3 kg off the neighbouring weigh-ins) left out silently while normal spikes stay in the average, so that a typo doesn't move my trend or trigger a message.

### Training plan and counted activity

14. As the user, I want my training plan seeded once from my CSV file, so that I don't have to type my week into chat.
15. As the user, I want to change my training plan in chat at any time, for this week or permanently, so that the saved plan follows my real life.
16. As the user, I want runs to count toward a day's target only when a run actually synced or I report it, so that optional easy runs need no message when I skip them.
17. As the user, I want lifting to count with a fixed kcal estimate per session when the session shows up in Hevy, so that lifting days get a fair target without me reporting anything.
18. As the user, I want wrestling to count as planned unless I say it didn't happen, so that the usual week needs no messages.
19. As the user, I want to report an extra session by just saying what I did and for how long (or with its kcal if I know them), so that unplanned activity is counted; code estimates the kcal when I don't give them (or the model, marked as its estimate, when code can't).
20. As the user, I want run calories discounted by my run discount, so that inflated Strava numbers don't overfeed me.
21. As the user, I want my daily target = base maintenance + counted activity + surplus, computed in code, so that targets are consistent and never invented by the model.
22. As the user, I want the coach to ignore MFP's own activity-adjusted goal, so that there is one source of targets.

### Phase start

23. As the user, I want to start the reverse with a command like "start reverse", so that the phase begins exactly when I decide.
24. As the user, I want the coach to prefill setup values it can read from my history (last diet intake, starting trend weight, maintenance estimate, main lifts) and ask me to confirm them, so that setup is quick and grounded in data.
25. As the user, I want it to ask only for what's missing, a few items per message, so that setup isn't an interrogation.
26. As the user, I want the coach to classify every exercise I log in Hevy as counting (compounds, machines, most bigger isolation work) or excluded (prehab/rehab and slow movers like lateral raises), and let me flip any, so that exercises that aren't meant to progress don't decide my calories.
27. As the user, I want to give run discount, wrestling kcal, lifting kcal, fat start, week-1 increase, optional time goal, photos on/off and waist at start, so that targets reflect my situation.
28. As the user, I want to set logistics once (weekly check-in day and time, evening reminder time, message limit, what "a while" means for the step floor), so that the coach messages me when it suits me.
29. As the user, I want a week-1 preview computed by code (average daily target, the MFP goal it will set, targets on rest / lifting / run / wrestling days, macros), so that I see exactly what I'm agreeing to.
30. As the user, I want nothing to change until I tap confirm, so that a half-finished setup has no effect.
31. As the user, I want the coach to refuse to start a draft phase with undecided values, so that cut or maintenance can't start half-defined.
32. As the user, I want to be told in advance that a 1–2 kg glycogen and water jump is expected in the first weeks, so that I don't panic.
33. As the user, I want setup values never filled with guesses, so that every number has a source.

### Weekly decision and report

34. As the user, I want one weekly report at my check-in time, so that non-urgent things come in one place.
35. As the user, I want the report to lead with the decision in plain words (not just a letter), so that I know what happens next.
36. As the user, I want my weight trend, weekly rate and target band in the report, so that I see where I stand.
37. As the user, I want weekly intake vs target and whether adherence passed, so that I know if the week counts.
38. As the user, I want macro, fiber and produce flags in one line each, so that quality issues are visible without nagging.
39. As the user, I want a training summary (how many counting lifts improved, PRs, stalls, deload signals), so that strength progress is part of the decision.
40. As the user, I want unusable weeks (too few weigh-ins, incomplete logs, sick or travel notes, stale data) explained in one sentence with what would make next week usable, so that I know the streak isn't lost.
41. As the user, I want glycogen-window weeks treated as "expected jump, not judged", so that no cut is proposed because of water.
42. As the user, I want a calorie change proposed only after the required confirmation (two usable weeks pointing the same way; one for gaining too fast), so that I don't react to noise.
43. As the user, I want skipped weeks (unusable, glycogen window, failed adherence, sport load) to neither count nor break confirmation, so that one bad week doesn't reset progress toward a decision.
44. As the user, I want change size of about 100 kcal when slightly outside the band and about 200 kcal when far off, so that steps match how far off I am.
45. As the user, I want "not gaining but lifts progressing" to keep calories unchanged, so that recomposition isn't mistaken for a stall.
46. As the user, I want "gaining but not progressing" to flag that training needs a look and not add calories, so that I don't gain fat for nothing.
47. As the user, I want "gaining too fast" to propose a decrease after one week, so that excess gain is corrected quickly.
48. As the user, I want the report to show what changed this week (what, why, what to expect, when it's re-checked), so that I can follow cause and effect.
49. As the user, I want deferred observations from daily jobs merged into the report, so that small notes arrive weekly, not daily.
50. As the user, I want the report to say what's due next week (waist, photos), so that I can plan check-ins.
51. As the user, I want every verdict stored with the facts it was based on and the rule ids applied, so that I can ask "why" later and decisions are replayable.
52. As the user, I want a missed weekly prediction (error above the prediction-miss threshold) to lower confidence and trigger a log check, so that surprising weeks get scrutiny.

### Proposals

53. As the user, I want proposals to arrive with approve, reject and counter buttons, so that deciding is one tap.
54. As the user, I want an approved calorie change to update my targets and set my MFP goal to the new average daily target, so that MFP shows the right number without me touching it.
55. As the user, I want the MFP goal write sent once, checked by reading it back, and never retried, so that MFP isn't changed twice by mistake.
56. As the user, I want approval to apply exactly once even if I double-tap, so that a change is never applied twice.
57. As the user, I want to reply with my own number to counter a proposal, so that I can steer within the guardrails.
58. As the user, I want the coach to say once (without arguing) when it disagrees with my counter, so that I know the trade-off.
59. As the user, I want to optionally give a reason when I reject, so that a rejected direction returns only after enough evidence and my reason is remembered.
60. As the user, I want the coach to refuse changes that break a guardrail (more than the max change outside a phase start, lockout after a change, confirmation not met, a rejected direction returning too early, unusable week, failed adherence) and say which one and when it could pass, so that rules are enforced by code, not by the model's mood.
61. As the user, I want unanswered proposals to leave my current plan unchanged, so that silence is safe.
62. As the user, I want an identical open proposal referenced instead of duplicated, so that I don't get the same card twice.

### Coach chat and context

63. As the user, I want to ask questions about my data and plan in plain language, so that I understand why the coach decided something.
64. As the user, I want to request a change ("can I go up 300?") and get it weighed against the data and guardrails, so that my requests are taken seriously but safely.
65. As the user, I want to send context any time in any form (sick, travel, creatine, knee hurts, felt flat, ate out), so that decisions respect my life.
66. As the user, I want context notes stored with dates and tags and confirmed in one line, so that I know what was recorded and its effect.
67. As the user, I want to mention a heavy week (e.g. a wrestling camp) and have it tagged as sport load, so that stalls that week are explained by load and no "raise calories" or "training needs a look" comes from it.
68. As the user, I want to tell the coach about a technique change, ROM change or exercise swap, so that the lift starts a new baseline instead of counting as a regression.
69. As the user, I want to pause tracking for an exercise I'm modifying around an injury, so that it neither counts nor flags.
70. As the user, I want to mark a planned session as skipped or add an extra one in chat, so that counted activity is right.
71. As the user, I want to record or change setup values in chat later, with calibration values (run discount, wrestling kcal, lifting kcal) going through a proposal, so that calibration changes are deliberate.
72. As the user, I want to see my coach profile with `/profile` and change it by telling the coach, so that I control what it knows about me.
73. As the user, I want medical, PED, supplement, technique and meal-tip questions declined in one line, so that the coach stays in its lane.
74. As the user, I want the coach to write in English, short and neutral, without motivational speeches or moralising, so that messages are quick to read.

### Daily messages

75. As the user, I want one evening reminder if food, weight or steps are missing for today, so that logs stay complete.
76. As the user, I want an evening note only when the week so far is off target, protein or fat is clearly off, or an entry looks implausible, so that most evenings are silent.
77. As the user, I want to be asked whether an implausible entry (e.g. 12,000 kcal) is a typo, so that odd logs are fixed in MFP before they distort decisions.
78. As the user, I want PRs named after a synced lifting session, so that progress is acknowledged.
79. As the user, I want a stall flagged once (three sessions without progress on a tracked lift), so that I know without being nagged every session.
80. As the user, I want to be asked "was this a reset?" with buttons after a sudden big load drop, so that baselines stay honest.
81. As the user, I want a daily message limit respected (except the reset question), so that the coach doesn't spam me.

### Measurements

82. As the user, I want a reminder the evening before my waist measurement and photos (when photos are on) are due every two weeks, plus a baseline photo set on the phase start day, so that body changes are tracked.
83. As the user, I want photo sets and waist values stored with their date, so that they're available when photo review is built.
84. As the user, I want the photo protocol reminder (same spot and light, hip height, morning, fasted, unpumped) with the photo prompt, so that sets are comparable.
85. As the user, I want to switch photos off at any time without anything else breaking, so that photos stay optional.

## Implementation Decisions

### Services and boundaries (ADR 0001)

- New service **coach**, its own uv project in the one pinned image, its own compose service. It polls `COACH_TELEGRAM_BOT_TOKEN` and accepts only `TELEGRAM_ALLOWED_USER_ID` (shared with the food bot).
- The coach is the only process that opens its SQLite database under `state/coach/`. Photos are stored under the same state directory.
- The coach reaches MFP and Hevy only through `fa-api`. The food bot is unchanged.
- The coach-skills package (skills, params, schemas, examples, tests template, validator) moves into the coach project and ships in the image. The coach loads skills, params and schemas at runtime from there.

### fa-api additions

- **Read endpoints for sync** (REST, on the existing api): compact per-day records for a date range: food totals (kcal, protein, carbs, fat, fiber, and produce grams if derivable, else null) plus whether the day is logged/complete, weight, steps, runs (kcal, distance, duration) from MFP; and Hevy lifting sessions with exercise id and title, and per-set load and reps. Hevy is read in pages of 5. Reads only.
- **`fitness_set_goal`** MCP tool on the tools endpoint (:8001, host-localhost only): sets the MFP calorie and macro goal using the MFP library's goal-setting call, and returns the stored goal. Not added to the food bot's read-tool allowlist; the coach model never receives it. Only coach code calls it, once per approved calorie proposal or confirmed phase start, then reads the goal back once to confirm. Never retried.

### Coach core (the test seam)

A `Coach` object that holds no Telegram or network code. Its inputs:

- `sync(now)`: pull new records from the api client into the database; record sync time and freshness.
- `run_due_jobs(now)`: run whichever scheduled jobs are due (weekly check-in, evening reminder and recap, training feedback after a newly synced session, waist/photo reminders).
- `on_message(text, now)` and `on_photo(...)`: chat input.
- `on_button(action, ref_id, now)`: button taps (approve, reject, counter, confirm/edit phase start, mark reset / not a reset).

Its outputs: messages with optional buttons in an **outbox**, plus state in the database.

Its dependencies, injected:
- **api client**: sync reads and `fitness_set_goal`.
- **model client**: wraps the Anthropic SDK; takes cached prefix + task skill + input JSON + tools, returns text, tool calls, or a schema-validated JSON object.
- **clock**.

The Telegram layer is a thin adapter: it turns updates into `on_message` / `on_button` calls and sends the outbox. A scheduler loop calls `sync` and `run_due_jobs` periodically.

### Claude (ADR 0003)

- Anthropic Python SDK. Endpoint and key from `COACH_ANTHROPIC_BASE_URL` / `COACH_ANTHROPIC_API_KEY`, falling back to `ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY`.
- `COACH_MODEL` (default `claude-sonnet-5-5`) for chat, evening recap, training feedback, phase start and the weekly report. `COACH_DECISION_MODEL` (default `claude-opus-5-5`) for the weekly decision (and later the reviews).
- Prompt layout per call: cached prefix (coach-core + active phase skill + tool definitions), then the task skill, then a short state snapshot and the input JSON. Chat keeps only a short history.
- The weekly decision returns JSON validated against the weekly-verdict schema; an invalid verdict is not acted on.
- The model never calculates: every number it sees comes from code-computed facts or tool results. Only exception: the kcal of a reported session code can't estimate (unknown activity, no trend weight), stored as a model estimate.

### Facts, rules and guardrails (code)

- Code computes daily facts and weekly facts per the schemas: 7-day averages, weekly rate, weigh-in count, logging completeness, weekly intake vs target, per-lift progression vs best of the last 3 sessions (heaviest working set with 4–20 reps; estimated 1RM when load differs; bodyweight added for dips and pull-ups; only exercises classified as counting; see ticket 08's Decisions), stalls, deload signal, maintenance estimate (back-calculated, 7,500 kcal ≈ 1 kg, windows of 3+ weeks, glycogen weeks excluded), phase week, glycogen window, gain band, carb remainder, predicted weight and prediction miss.
- Params: coach-core params merged with the active phase's params (phase wins), passed inside the facts.
- Macros: protein and fat in g/kg of the current 7-day trend weight, recalculated weekly; carbs take the remainder.
- Code-only rules (no model call): weigh-in outlier marking, missing-log reminder (one per day), data-freshness check, waist and photo due dates, applying approved proposals, setting the MFP goal.
- `propose_change` runs the guardrails in code (max change except a phase's first change, lockout, confirmation, rejected-return, unusable week, adherence gate, invalid calibration values) and stores the proposal as `open` or `blocked_by_guardrail` with violations. It never applies anything.
- Approval uses one atomic claim per proposal (as the food bot's cards do), so an approval applies exactly once. The same claim will serve the later web page.

### Changes to the skills package (land with the code that needs them)

- **Sport load is a context-note tag.** The weekly decision treats a week with a `sport_load` note as a skipped week for confirmation (neither counts nor breaks). It no longer resets the streak, and it still makes no C/D call from that week. The `set_week_sport_load` tool is removed; the coach-skills README assumption is updated.
- **Prediction miss is a fixed threshold.** A new core param (0.3 kg) replaces "error > band width"; schema, README and skills updated.
- **Lifting kcal.** A new setup value, lifting kcal per session, in core params, the phase-setup schema and the phase-start skill.
- **Training plan.** `repull_training_plan` is removed: the plan is seeded once from the CSV and then changed only through chat (`update_training_plan`, `set_session_status`).
- **Counted activity.** Optional planned sessions count only when they happen; lifting counts when a Hevy session exists; wrestling counts as planned unless reported skipped.
- **Language.** English.
- Field names may be renamed to fit the code; schema, skills, examples and the validator change together and the validator stays green.

### Training plan

- Seeded once, at first start (or on an explicit setup step), from a CSV file in the repo's data folder, holding the current export of the user's sheet. The current sheet has a week grid (day → sessions with times, optional runs) above per-session exercise lists. After seeding, the saved plan lives in the database and changes only through chat.
- The exercise lists are used only to help the coach classify exercises at phase start.

### Telegram

- Coach replies are plain text with light formatting. Buttons: approve / reject / counter on proposals, confirm / edit on phase start, mark reset / not a reset on training feedback.
- After any tap, the card's buttons are removed and the outcome is shown.
- `/profile` shows the coach profile.

## Testing Decisions

- **One seam: the Coach core.** Tests drive `sync`, `run_due_jobs`, `on_message`, `on_photo` and `on_button` with fakes. A fake api client returns daily records and records `fitness_set_goal` calls. A fake model client returns scripted replies, tool calls and verdicts, and records exactly what it was given. A fake clock moves time. An in-memory outbox collects messages. Assertions are on the outbox, stored state (phase, targets, proposals, verdicts, context notes), facts handed to the model, and goal writes.
- **What a good test looks like:** observable behaviour only, through that seam. No asserting on internal helpers or SQL. Facts handed to the model are validated against the JSON schemas.
- **Covered through the seam:** facts computation (averages, rates, completeness, progression vs best of last 3, stalls, deload, maintenance estimate, prediction miss), confirmation counting with skipped weeks, every guardrail, phase start (preview, confirm, nothing applied before confirm), approve / reject / counter, exactly-once approval and goal write (including a failed goal write that isn't retried), counted activity rules, sport-load notes, evening silence vs reminder, and the daily message limit.
- **Prior art:** the food bot's card tests: a recording fake for MFP, one-time execution, nothing written without a tap, and failures reported, never retried.
- **Run:** `docker compose run --rm test` runs the coach tests next to the food bot's, with no network. The skills validator runs in the same test run.
- **Not unit-tested in v1:** the Telegram adapter and the new fa-api endpoints (thin pass-through, checked once by hand against live MFP and Hevy). Replay tests on labelled past weeks with the real model come later.

## Out of Scope

- Block review, phase review and photo review (body-fat estimates). Photos and waist are collected and stored only.
- Cut and maintenance phases (drafts stay drafts; phase start refuses them).
- The coach page in the web UI, with full editing and approvals, through a coach HTTP API proxied by fa-api under `/api/coach/`, approvals sharing the same claim, and tailnet-only access (ADR 0001). This comes right after v1.
- A live Google Sheet integration for the training plan.
- Replay tests on 10–15 labelled weeks as an automated check.
- Changes to the food bot.
- Everything listed under "Dropped" and "Left out" in `SPEC.md`.

## Further Notes

- Lifts come from Hevy, everything else from MFP (ADR 0002).
- The coach never writes to the MFP food diary; odd log entries are pointed out for me to fix in MFP.
- Assumptions accepted as written: "far off" = 0.1 kg/week beyond the band, stale after 36 h, deload at 2 declining lifts, reset question at a 15% drop, best of last 3 sessions, macros from the 7-day trend weight, and adherence-gate weeks skipped for confirmation. The two cut and maintenance assumptions wait for those phases.
- Setup values still to collect at phase start: which lifts count (classified by the coach), starting calories, starting trend weight, maintenance estimate, run discount, wrestling kcal, lifting kcal, fat start, week-1 increase, time goal, photos on/off, waist, and logistics.
