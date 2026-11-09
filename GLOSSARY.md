# Fitness aggregator

Personal fitness data from MyFitnessPal and Hevy, a food-logging bot, and a coach that monitors the data and proposes plan changes the user confirms.

## Bots

**Food bot**:
The Telegram bot that logs food into the MyFitnessPal diary after the user taps ✅ on a card.
_Avoid_: bot (alone), assistant

**Coach**:
The separate Telegram bot and service that watches the user's data, reports, and proposes changes to the plan; it never logs food.
_Avoid_: coaching agent, coach bot

**Diary change**:
Foods to add to or remove from the MyFitnessPal diary, shown by the food bot as a card and written only after ✅.
_Avoid_: proposal (that is the coach's)

**Proposal**:
A change to calories or calibration values that the coach suggests and that takes effect only after the user approves it.
_Avoid_: suggestion, change request, card

**Phase**:
A stretch of the plan with one goal and its own rules (reverse into bulk, cut, maintenance), started by the user's command and ended by the user.
_Avoid_: cycle, block (a block is a training block)

**Context note**:
A dated, free-form note from the user about life, body or training (illness, travel, a camp, creatine) that every later decision respects.
_Avoid_: log entry, journal

## Plan

**Training plan**:
The saved default week of lifting sessions and sports, seeded once from a CSV file and from then on changed only in the coach chat.
_Avoid_: workout plan, schedule

**Planned session**:
A lifting session, run or wrestling session in the training plan; optional ones count only if they actually happen.
_Avoid_: workout, training day

**Daily target**:
A day's calorie target: base maintenance plus that day's counted activity plus the phase's surplus.
_Avoid_: goal, calorie goal

**Counted activity**:
The calories a day's sessions add to its daily target: runs at their synced calories times the run discount, wrestling and lifting at a fixed estimate per session, and extra sessions the user reports.
_Avoid_: exercise calories, burned calories

**MFP goal**:
The calorie and macro goal stored in MyFitnessPal; the coach sets it to the average daily target and otherwise ignores it.
_Avoid_: target (a target lives in the coach, not in MFP)

## Weekly decision

**Usable week**:
A week with enough weigh-ins, complete logs and no disrupting context (illness, travel) to base a calorie decision on.
_Avoid_: valid week, good week

**Sport-load week**:
A week a context note marks as high sport load (e.g. a wrestling camp); stalls that week are put down to load, and it proposes no changes.
_Avoid_: heavy week, camp week

**Confirmation**:
The run of consecutive usable weeks pointing the same direction that a calorie change needs; skipped weeks (unusable, glycogen window, failed adherence, sport load) neither count nor break it.
_Avoid_: streak, two-week rule
