# Personal Coaching Agent – Scope v0

Nov 8, 2026 · @Flo

## Core design

A personal coaching agent with access to weight, training, steps, food intake and activity data. It monitors, reports and proposes changes; I confirm every plan change. Keep it lean: anything not clearly needed stays out.

- **Users:** personal use only. No escalation logic, no PED topics.
- **Three loops:**
  1. Continuous monitoring: silent on each new data point (clean data, update trends, check triggers).
  2. Scheduled touchpoints: daily, weekly, every 2 weeks, per training block, per phase.
  3. Event-triggered actions: a threshold is crossed, so the agent informs, asks or proposes.
- **Phases:** one phase-agnostic core plus a config per phase (reverse, bulk, cut, maintenance), each defined as a phase skill. First build: reverse into bulk.
- **Authority:** the agent proposes, I confirm. Data cleanup happens silently.
- **Context log:** free-form, dated notes (illness, travel, creatine, alcohol, how I feel, anything else). Added anytime in chat, no fixed format. Every decision takes it into account.
- **Training data:** read from my training log. I can correct or add sessions in chat if something wasn't logged.

**Phase start inputs**

- Which lifts count for A–E: the agent classifies every Hevy exercise as counting (compounds, machines, most bigger isolation work) or excluded (prehab/rehab and slow movers like lateral raises, tibialis raises, abs); I can flip any
- Starting calories (last diet intake)
- Starting trend weight
- Maintenance estimate from the last diet weeks
- Training and sport plan

A phase starts with a Telegram command (e.g. "start reverse"). The agent collects any missing setup values, shows the week 1 targets, and I confirm.

## Scheduled cadence

Most days the agent sends nothing; it messages only when something is missing or actionable.

| When | What the agent does |
| --- | --- |
| Daily, on weigh-in | Updates the 7-day average; only clear typos (> 3 kg off the neighbouring weigh-ins) are left out, silently. Normal spikes stay in the average |
| Daily, evening | One reminder if food, weight or steps are missing |
| After training | Optional quick check. It can be skipped; the agent works from the training log |
| Daily, when relevant | Actionable note only: something needs attention, or a PR |
| Weekly | Auto report, A–E decision with reasoning, any approved change (what, why, what to expect, when it's re-checked), expectations for the next week |
| Every 2 weeks | Asks for waist (and photos, if on); re-estimates maintenance |
| Each training block (4–6 weeks) | Block review: lift trends, stalls, fatigue and deload signals, session volume note |
| Every 8–12 weeks or phase end | Phase review: progress vs plan, photo comparison, goal check |

## Decision logic: weight vs strength (A–E)

The weekly decision compares the weight trend with gym progression, evaluated every 7 days. Any change is a proposal I confirm.

| Scenario | Weight | Gym progression | Proposal |
| --- | --- | --- | --- |
| A | Gaining (on target) | Yes | Keep calories and activity unchanged for the next 7 days |
| B | Not gaining | Yes | Keep unchanged; strength gains show muscle building is working |
| C | Not gaining | No | Raise calories |
| D | Gaining | No | Don't add calories; flag that training needs a look |
| E | Gaining too fast | Any | Lower calories; the last increase was set too high |

**Definitions**

- Weight trend (7-day averages, outside the glycogen window), judged against the phase band: weeks 1–6 on target +0.1–0.3 kg/week, after that +0.2–0.4 kg/week. Below the band counts as not gaining. Between the top of the band and +0.5 kg/week is watched, not acted on. Too fast: above +0.5 kg/week.
- Gym progression: at least half of the counting lifts improved, each vs the best of its last 3 sessions. Excluded lifts (prehab/rehab, slow movers) never decide it. Each lift uses its own sessions, whenever they happened; a lift counts if trained in the last \~2 weeks. Single-lift stalls are flags only.
- Confirmation: a calorie change needs two consecutive usable weeks pointing the same way. Scenario E can trigger after one week. The week after a change is week 1 of the new window, so the earliest next change is after 2 weeks (E after 1).
- Unusable weeks (too few weigh-ins, incomplete logs, a sick or travel note) are skipped for decisions; the usable weeks around them still count as consecutive.
- Change size: \~100 kcal when slightly outside the band, \~200 kcal when far off. Scenario C uses calories by default, not activity.
- Sport load: I mention a heavy week (e.g. a wrestling camp) and it's stored as a `sport_load` context note. Those weeks are skipped for confirmation (they neither count nor break it); stalls are explained by load, and no C or D proposals are made from them.
- Scenario D or a deload signal: the agent only flags that training needs a look; I make any changes.
- A–E steers toward the gain band; there is no separate gain-rate calibration.

## Nutrition engine

Macros are set by phase. Protein and fat are fixed in g/kg; carbs take whatever calories remain.

| Setting | Reverse / bulk | Cut |
| --- | --- | --- |
| Protein | \~2.0 g/kg | \~2.5 g/kg |
| Fat | 0.8–1.0 g/kg (cap 1.0) | \~0.6 g/kg (floor) |
| Carbs | Remaining calories | Remaining calories |

Carbs (g) = (target kcal − protein g × 4 − fat g × 9) ÷ 4.

- Calorie changes go to carbs (step sizes in Definitions) once fat is at its cap or floor. The activity lever is 1–2k steps or 10–15 min easy cardio.
- When unsure, pick the smaller increase: a shortfall is fixed next week, extra fat gain isn't.
- Flexible tracking: the agent works with numbers, not a fixed meal plan.
- Off-plan meals: just log them, no special rules.
- No fluid tracking. Daily macros and reasonable micronutrients matter; a single meal without protein doesn't.

## Reverse and bulk settings

One continuous phase: the reverse is the first stage of the bulk.

- Week 1: +300–400 kcal, activity unchanged. No big jumps.
- After that: A–E decisions (see Definitions).
- Gain rate: +0.1–0.3 kg/week in weeks 1–6, then +0.2–0.4 kg/week. A–E does the steering within this band.
- An early 1–2 kg glycogen and water jump is expected. The glycogen window is the first 2 weeks after the diet ends.
- Optional time goal (e.g. a 30-week bulk); the agent advises near it, and I decide.
- Body fat: as it nears \~23–24%, the agent can advise a mini-cut or ending the bulk. This is advice, not a hard stop; I can choose to continue. Body fat comes from my own estimate or the agent's estimate from photos, never from the scale. The agent estimates it at every photo check-in (every 2 weeks).

## Training data rules

- Progress = more load or reps at the same execution. Micro-progressions count.
- A session is judged by its heaviest working set with 4–20 reps (warm-ups never count). More load or reps and neither less = improved (even +0.5 kg); less of either and neither more = declined; both equal = same. Only when load goes up and reps down (or the reverse): estimated 1RM (Epley), within ±1% = same.
- Every exercise logged in Hevy is recorded and classified as counting or excluded (excluded: still logged and PRs named, no stall flags, no effect on calories). Alternatives (e.g. pull-ups vs lat pulldown) are separate exercises with their own history.
- A new exercise's first session starts its history: no PR, not judged.
- After more than ~2 weeks off an exercise, the first session back isn't judged; the next one is compared with the pre-break best.
- A session at another gym or on another machine: I say so and that day isn't judged (or I don't log it, or log a separate Hevy exercise).
- A technique or ROM change, or an exercise swap, starts a new baseline. It counts as neither progress nor regression.
- Dips, pull-ups and similar: bodyweight gained counts as added load.
- A movement modified around an injury pauses tracking for that exercise.
- Stall: 3 sessions without progress on the same exercise → flag.
- Session volume: noted in the block review only (more than 20 sets per session or more than 4 sets per muscle per session).
- RIR isn't logged, so no RIR checks.

## Photos and measurements (optional)

Photos are on at the start of the reverse and may be switched off at any point, so nothing else depends on them.

- Protocol reminder: same spot and light, camera at hip height, morning, fasted, unpumped. Waist and photo reminders come the evening before they're due; a baseline photo set is due on the phase start day.
- Compare like for like, at similar leanness (e.g. end of cut vs end of cut). Mid-bulk vs start is unreliable.
- Looking softer mid-bulk: point back to logbook progress instead of reacting.
- Recomp rule: stable weight with a leaner waist or photos means muscle gained.

## Triggers

**Weight**

- Trend above or below the target rate → feeds the A–E decision.
- Unexpected trend reversal → check logging and adherence before proposing anything.
- Big single-day spike → short explanation (sodium, carbs, context log), no action.
- Reverse phase: knows a 1–2 kg glycogen and water jump is expected early on, labels it as such and doesn't propose cuts because of it.

**Intake**

- Adherence gate: calorie changes only when all eating was logged and the weekly average intake is within \~±5% of the weekly target; otherwise address adherence first.
- Consistent overshoot or undershoot of a target → ask why.
- Macro and quality checks: daily protein, fat and carbs vs target, fiber 0.3–0.5 g/kg, produce at least 500 g/day. No alarm over single meals.
- General bad-pattern detection (weekends included), no hard weekday/weekend rule.

**Training**

- The A–E scenarios (above).
- Single-lift stall (3 sessions without progress) while others progress → flag it, judged with that exercise's normal behavior in mind.
- Several lifts declining over 2+ sessions → fatigue or deload signal.
- Missed-session patterns → suggest a schedule change.
- No technique cues; the agent can't see me train.

**Activity**

- Daily target = base maintenance + that day's activity + surplus. Runs: Strava/MFP calories × a discount (e.g. 75%). Wrestling: a fixed estimate per session, counted as planned unless I say I skipped it. Lifting: a fixed estimate per session, counted when the session is in Hevy. Runs count only when Strava synced one (HealthKit duplicates never count) or I report it. Other sessions: I just say what I did and for how long; kcal are estimated (code from activity × duration × trend weight, else the model's estimate), and a number I give always wins. At phase review the agent proposes new run-discount and wrestling values when they drift; I confirm. Base maintenance excludes activity, which the back-calculation subtracts.
- Steps are a measuring tool, not a target to enforce. Large swings (2k to 30k) are expected and not a problem.
- Soft step floor of \~10k: a gentle note only if steps stay very low for a while and no other training happened.

**Fat gain**

- Body-fat advice: see Reverse and bulk settings. Waist trend is reported in reviews but doesn't trigger advice.
- The agent can raise concern from photo comparison, if photos are on.

## Calibration and guardrails

**Calibration**

- Running maintenance estimate, back-calculated from logged intake vs weight trend, using 7,500 kcal ≈ 1 kg over windows of at least 3 weeks, excluding glycogen weeks. A rough input; A–E does the steering.
- Prediction tracking: code predicts each week's weight and checks whether past changes did what they should.

**Guardrails**

- Minimum data: enough weigh-ins (e.g. 5+ per week) and complete logs before trusting a trend.
- Lockout: the week after a change is week 1 of the next two-week window (see Definitions).
- Noise filter: no decisions off single days, salty meals, travel, illness, bad sleep or alcohol.
- Message limit: non-urgent items are batched into the weekly report.
- Explain conflicts: when signals disagree (e.g. weight up, waist down), explain instead of acting.
- Unanswered proposal: the current plan stays.

## On-demand behaviors and reports

**On-demand**

- Clarify odd logs: asks about implausible entries (e.g. a 12,000 kcal day: typo or real?).
- Ask when unclear: requests waist, photos or context only when the data doesn't explain itself.
- Evaluate my requests: when I ask for a change, it weighs it against the data and shows trade-offs.
- Goal check at each phase review.
- Rejected proposal: can return only if the next two usable weeks still point that way; my reason is noted.
- Counter-proposal: I can reply with my own number; it's applied if it passes the guardrails, and the agent says if it disagrees.

**Reports**

| Report | When | Contents |
| --- | --- | --- |
| Daily note | Only when actionable or a PR | One short message |
| Weekly report | Every week | Weight trend vs target, adherence, intake, steps, training summary, A–E decision with reasoning, any approved change (what, why, what to expect, when it's re-checked), expectations for the next week |
| Block review | End of each training block | Lift progress, stalls, fatigue, session volume note, what's next |
| Phase review | Every 8–12 weeks or phase end | Progress vs plan, maintenance estimate, photo comparison, goal check, next phase |

## Other phases (draft)

Cut and maintenance reuse the core: same timing rules, adherence gate, guardrails and reports. Exact numbers get tuned in their skills when the phase comes up.

**Cut**

- Target: \~750 kcal/day deficit to start.
- Macros: protein \~2.5 g/kg, fat \~0.6 g/kg floor, carbs = remainder.
- Stall with adherence fine: carbs first, −25–50 g (100–200 kcal) per step.
- Strength: holding lifts = success; several lifts dropping flags the deficit or recovery.
- Timing: two-week confirmation, 7-day lockout, unusable weeks skipped.
- A mini-cut during a bulk uses this same config; I end it.

**Maintenance**

- Flat = within ±0.1 kg/week; propose a change on drift beyond ±0.2 kg/week for two weeks.

**Phase ends (all phases)**

- Ending is my call. The agent advises at a target (body fat, weight) or a time goal (e.g. a 30-week bulk), and when hunger notes pile up in a cut.
- After a phase ends, the agent asks what comes next.

## Implementation approach

Code computes the numbers and enforces a few guardrails; skills make the decisions and do all interpretation. Builds on the existing FastAPI + Telegram + MyFitnessPal agent, using the Claude API directly.

| Part | Where |
| --- | --- |
| Sync from MyFitnessPal (food, weight, Strava runs, steps) and Hevy (lifts) into own database. Both are data sources only | Code |
| Scheduler and Telegram buttons; two Telegram chats, one for the coach and one for food logging | Code |
| Weekly facts: 7-day averages, weekly rate, weigh-in count, logging completeness, weekly intake vs target, per-lift progress vs best of last 2–3, maintenance estimate, phase week, gain band, carb remainder, predicted weight | Code |
| Data freshness: stale or incomplete sync → unusable week, notify me | Code |
| Usable week | Code counts weigh-ins and logs; skill reads context notes |
| Daily checks | Code rules (outliers, missing logs); daily skills for the evening day recap and training feedback |
| A–E decision, sport load, mixed weeks, change size, stall flags, body-fat advice | Skill with hard rules |
| Reports, proposals, explanations, photo review, context tagging, Q&A | Skill |
| Guardrails in the propose\_change tool: nothing applied without my OK; max 200 kcal per change, except a phase's first change (follows the phase skill); lockout and two-week rule | Code |
| On approval: set the MFP calorie goal to the average daily target | Code |

- **Targets live in the app,** never MFP's activity-adjusted goal. Daily target = base maintenance + that day's activity + surplus (see Triggers, Activity). Training plan: a saved default week, seeded once from a CSV export of my Google Sheet (a live Sheet integration comes later); after that it changes only through Telegram, for this week or for good.
- **Phase skill = phase config:** rules in prose plus a parameter block that code reads too. The prose refers to parameters by name and never repeats the numbers.
- **Lift data** has per-set load and reps with stable exercise IDs. Baseline resets are marked by a Telegram command or button, and the agent asks after a sudden big load drop.
- **Code calculates what it can;** targets, guardrails and weekly facts are always code. The model gets the weekly facts and returns a structured verdict (scenario, rules applied, proposal, confidence), stored with those facts. Where code has no way to compute a convenience number (e.g. kcal of an unusual reported session), the model may estimate it; the estimate is marked as such and I can correct it.
- **Photos:** each body-fat estimate sees the previous photo set and estimate, so it judges relative change.
- **Context per call:** stable cached prefix, a short state snapshot from code, tools that return aggregated data, short chat history.
- **Memory:** numbers and decisions in the database; context log with tags; a small coach profile I can see and edit.
- **Testing:** 10–15 labeled past weeks (normal, glycogen, sick, scenario D and so on) replayed through the skill after every edit.
- **More coaches later:** each a module with its own skills and one owner per variable, sharing data and the context log.

## Open and dropped items

**Open**

- [ ] Review at the first phase review whether photos are worth keeping.
- [ ] Setup values (phase-start inputs, run discount, wrestling estimate) are given to the agent at setup and recorded there, not in this spec.
- [ ] Finalize cut and maintenance numbers in their skills (draft in Other phases).
- [ ] Fine-tune per-exercise stall rules over time.
- [ ] Refine each item one by one for the final spec.

**Dropped for now**

- Escalation (medical, psychological, injury) and PED topics
- Daily biofeedback scores (replaced by the context log)
- Hard weekday/weekend split (covered by general pattern detection)
- Seasonal NEAT adjustment and device-change baseline reset
- Logging-drift detection and calendar awareness
- Waist gain per kg, meal timing vs performance, food variety check
- One-change-at-a-time rule, event freeze
- Technique suggestions

**Left out from the training principle docs**

- Fluid and salt targets, supplements, protein-per-meal rules
- Off-plan meal swap rules; appetite, hunger and busy-day tips
- RIR checks, exercise-swap flag, cardio-limited-set check, separate gain-rate calibration, separate change notices
- Week-1 activity reduction give (calories-only start chosen)
- Sleep data (not tracked)
- Genetics, PED content, competition, multi-year muscle prioritization, mindset scripts
- Claims treated as dubious: Candida eating carbs, dehydration tears, blood sugar as the cause of low appetite, a blanket HIIT ban
