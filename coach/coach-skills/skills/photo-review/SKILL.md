---
name: photo-review
description: Runs once a photo set has arrived during the active phase (photos are due every measurements.photos_every_weeks weeks, when measurements.photos_enabled). Compares the new set with the earlier set code picked like for like, estimates body fat as a range and checks the photo protocol. Load with coach-core and the active phase skill. Output photo_review.schema.json.
---

# Photo review

Input (code computes all of it): `photo_set` (date, number of photos, phase week),
`comparison_set` (the earlier set code picked, or null: `picked` is `similar_leanness`, the
latest set whose estimate is within ±2 % of the latest estimate, or `phase_start`, the phase
start set when none is; with that set's `estimate`), `previous_estimate` (the latest estimate
up to this set: the user's own wins for its date), `waist` (newest first), `phase`, `params`.
The images follow the input, each after its label: "New set <date>, photo n", then
"Comparison set <date>, photo n".

## Steps

1. **PH-PROTOCOL** – Check the protocol: same spot and light, camera at hip height,
   morning, fasted, unpumped, same poses and views. List deviations in
   `comparability_issues` and set `comparability` (`no_previous` without a comparison
   set). Add a one-line fix in `notes` if needed.
2. **PH-RELATIVE** – Judge change relative to the comparison set and its estimate, not
   from scratch: `leaner`, `similar`, `softer`, or `not_comparable` (no comparison set, or
   the protocol broke badly). Anchor the new range near the comparison set's estimate
   (and `previous_estimate`) unless the change is clear. A `phase_start` comparison at a
   different leanness is less reliable: say so.
3. **PH-ESTIMATE** – Give `bf_estimate` as a range (low–high, at most about 3 % wide), with
   honest `confidence`. Photo estimates are rough; say so when confidence is low. Never use a
   scale's body-fat reading. Use the waist trend as a cross-check, not as the estimate.
4. **PH-PHASE** – Apply the phase's reading rules: during a bulk, softer or flatter is
   expected (RB-SOFT) – point to logbook progress; stable weight with a leaner look = muscle
   gained (RB-RECOMP).
5. **PH-NOTES** – 2–4 plain sentences for the user: what changed, how reliable it is, any
   protocol fix. Code sends `notes` with the range, and stores the range's midpoint as the
   estimate. `photo_set_id` and `previous_photo_set_id` are the sets' ids from the input.

## Rules

- Describe the physique neutrally (fat level, definition, fullness). No comments on
  attractiveness, no comparisons to other people.
- Don't give body-fat advice (mini-cut, ending the bulk): code sends it when the estimate
  reaches the phase's `body_fat.advise_near_pct`, at most once per 4 weeks.
- If photos are disabled, this skill is not called; nothing else depends on it.
