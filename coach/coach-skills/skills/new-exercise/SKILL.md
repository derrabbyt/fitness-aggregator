---
name: new-exercise
description: Runs when an exercise the coach hasn't classified yet first shows up in a synced Hevy session during a phase. Classifies it as counting or excluded with classify_exercises and tells the user in one short message. Load with coach-core and the active phase skill. Input new_exercises (id, title, Hevy type, sessions) and the already classified exercises; output plain text.
---

# New exercise

Every exercise logged in Hevy is recorded. Only exercises classified as `counts` decide
weekly progression (`training.progression_met`), stalls and the deload signal; `excluded`
ones are still logged and their PRs named.

## Steps

1. **NE-CLASSIFY** – For each item in `new_exercises`, call `classify_exercises` once with
   all of them:
   - `counts` (the default): compounds, machines and most bigger isolation work
     (curls, rows, presses, leg curls and extensions …)
   - `excluded`: prehab/rehab and slow movers – lateral raises, tibialis raises,
     Copenhagen plank, hip flexor raises, abs, plyometrics like pogo hops and box jumps
   Use `classified_exercises` to stay consistent with earlier calls (an alternative of
   a counting lift usually counts too). Give a few words as `reason`.
2. **NE-TELL** – Reply with one short message: the new exercise(s), how each is
   classified and why in a few words, and that the user can flip any in chat
   ("count lateral raises after all"). No numbers, no advice.

## Rules

- **NE-JUDGEMENT** – This is your judgement; don't ask the user first.
- **NE-SHORT** – One message, a line per exercise at most.
