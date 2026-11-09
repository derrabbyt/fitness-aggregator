---
name: photo-review
description: Runs at each photo check-in (every measurements.photos_every_weeks weeks, when measurements.photos_enabled). Compares the new photo set with the previous set and previous estimate, estimates body fat as a range, checks the photo protocol, and applies the phase's body-fat advice rule. Load with coach-core and the active phase skill. Output photo_review.schema.json.
---

# Photo review

Input: the new photo set (images), the previous photo set (images), the previous
`photo_review` (or the user's own last estimate), phase week, waist trend, `params`.

## Steps

1. **PH-PROTOCOL** – Check the protocol: same spot and light, camera at hip height,
   morning, fasted, unpumped, same poses and views. List deviations in
   `comparability_issues` and set `comparability`. Add a one-line fix in `notes` if needed.
2. **PH-RELATIVE** – Judge change relative to the previous set and previous estimate, not
   from scratch: `leaner`, `similar`, `softer`, or `not_comparable` when the protocol broke
   badly. Anchor the new range near the previous one unless the change is clear.
3. **PH-ESTIMATE** – Give `bf_estimate` as a range (low–high), with honest `confidence`.
   Photo estimates are rough; say so when confidence is low. Never use a scale's body-fat
   reading.
4. **PH-PHASE** – Apply the phase's reading rules: during a bulk, softer or flatter is
   expected (RB-SOFT) – point to logbook progress; stable weight with a leaner look = muscle
   gained (RB-RECOMP).
5. **PH-CEILING** – Set `advise_ceiling` if the range reaches the phase's
   `body_fat.advise_near_pct`. The advice itself (mini-cut or end the bulk) goes in `notes`
   and is advice only.
6. **PH-NOTES** – 2–4 plain sentences for the user: what changed, how reliable it is, any
   protocol fix. Code sends `notes` to the coach chat.

## Rules

- Describe the physique neutrally (fat level, definition, fullness). No comments on
  attractiveness, no comparisons to other people.
- If photos are disabled, this skill is not called; nothing else depends on it.
