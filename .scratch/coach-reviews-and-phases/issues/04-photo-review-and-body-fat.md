# 04: Photo review and body-fat estimate

**What to build:** After a photo set arrives: the model gets the set and the most recent set at similar leanness (estimate within +-2 %, else the phase start set) as images plus the waist trend, and stores a body-fat estimate (source model). Chat tool `record_body_fat(pct, date)` stores the user's (wins for its date). In a bulk, an estimate >= `bulk.body_fat_advice_pct` (23) sends mini-cut / end-bulk advice, at most once per 4 weeks.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Model client supports image input (fake in tests)
- [x] Tests: like-for-like pick, user estimate wins, advice threshold and 4-week limit
- [x] Skill `photo-review`; validator green
- [x] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.

## Comments

Built in `features/photo_review.py` (tests `coach/tests/test_photo_review.py`). No migration.

- **Image input:** `ports.Image(label, data, media_type)`, `ModelRequest.images`,
  `coach.ask(..., images=...)`. `model.py` puts each image after its label text in the
  user turn, after the input JSON (base64). The fake records them on the request.
- **When it runs:** photos arrive one by one, so job `photo-review` reviews the latest set
  once no new photo came for 10 minutes (`SETTLE`, an assumption), during the active phase
  with photos on, for a set dated on/after the phase start and at most 2 days back (no
  backlog after a deploy). Once per set date (`once`); a model failure or an invalid answer
  is logged and not retried (the next set gets its review). Decision model, schema
  `photo_review`.
- **Like for like:** the reference is the latest winning estimate up to the set's date
  (the user's own counts, also one given that day before the review). The comparison is
  the most recent earlier set whose estimate is within ±2 % of it; else the phase start set
  (first set on/after the start date); else none (`no_previous`).
- **Storing:** the range's midpoint (to 0.5 %) is the set date's model estimate, linked to
  the review; the review (key = set date, period = comparison date..set date) is the
  model's `notes` plus "Body-fat estimate: low–high % (confidence; compared with ...)".
  Facts keep the input and the model's JSON.
- **Advice:** the threshold is the existing phase param `body_fat.advise_near_pct` low end
  (reverse bulk [23, 24]; cut and maintenance null = never), not a new
  `bulk.body_fat_advice_pct`. Code sends a fixed advice text (mini-cut / end the bulk,
  advice only, "start cut") when the *newest* estimate (photo or the user's, the winning one
  for its date) reaches it; exempt from the daily limit, kind `body-fat-advice`, and the
  4-week limit counts from the last such message (`unprompted_messages`). A user estimate
  through `record_body_fat` triggers it too. Schema `photo_review`: `advise_ceiling` dropped
  (code decides); the skill no longer gives advice.
- **record_body_fat(pct, date?)**: date defaults to today, future dates and values outside
  3-50 % refused; returns `photo_estimate_pct` (what it overrides) and `advice_sent`.
  Rule CC-BODY-FAT in coach-chat, TOOLS.md row.
- **Cut fallback (ticket 05):** a body-fat goal may leave out `current_body_fat_pct`
  (schema: no longer required); `start_phase` then takes the latest estimate up to today
  (`body_fat.estimates`, the user's winning) and the preview's setup keeps the value used.
  Without any estimate `start_phase` refuses and asks for it.
- **Weekly facts:** `measurements.latest_bf_estimate` is now filled from the latest estimate
  up to the week's end (low = high = the stored value; source photo/user), so RB-BF and
  the phase review see it. RB-BF notes that code already sends the advice.
