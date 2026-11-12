# 01: Reviews table and their place on the web

**What to build:** Migration `reviews (id, kind block|phase|photo, phase_row_id, period_start, period_end, facts JSON, text, created_at)`; once-keyed send helper; the Week read model lists reviews sent in the week (collapsed like the report); Setup › Measurements lists body-fat estimates (table `body_fat_estimates (date, pct, source model|user, review_id)`).

**Blocked by:** None

**Status:** ready-for-agent

- [x] Migration + schemas + examples
- [x] Week view and Setup measurements show them (tests)
- [x] Web UI: collapsed review on Week, estimates list
- [x] Tests green

Spec: `.scratch/coach-reviews-and-phases/spec.md`.

## Comments

**API for tickets 02-04** (tests: `coach/tests/test_reviews.py`).

`fa_coach/reviews.py` (table `reviews`, migration `25_reviews.sql`):

- `reviews.sent(coach, kind, key) -> bool`: check before calling the model, so a
  review isn't written twice.
- `reviews.send(coach, *, kind, key, phase_row_id, period_start, period_end, facts,
  text, now, buttons=(), ref=None) -> int | None`: stores the row and sends `text`
  once per (kind, key); returns the review id, or None when the key was already used
  (nothing sent). `kind` is `block` | `phase` | `photo` (else ValueError). `key` is
  the caller's, stable across retries; suggested: block `"<phase id>:<n>"`, phase
  `"<phase id>:week-10"` / `"<phase id>:end"`, photo the set's date. Periods are ISO
  date strings; `facts` any JSON-able dict.
- `reviews.get(coach, id)`, `reviews.sent_between(coach, start, end)` (local send
  dates, inclusive, oldest first): dicts `{id, kind, phase_row_id, period_start,
  period_end, facts, text, created_at}`.

`fa_coach/body_fat.py` (table `body_fat_estimates`, same migration):

- `body_fat.problem(pct) -> str | None` (range `PCT` = 3-50, as `photo_review`'s
  `bf_estimate`): for the chat tool `record_body_fat` to answer with.
- `body_fat.add(coach, day, pct, source, now, review_id=None) -> int`: source
  `model` | `user`; ValueError on a bad pct/source.
- `body_fat.estimates(coach)` (newest first) and `body_fat.on(coach, day)`: one
  winning estimate per date, `{date, pct, source, model_pct}`; the user's latest
  wins over any model estimate for that date, else the latest model one;
  `model_pct` is the model estimate a user's overrides.

**Decisions**

- Reviews are sent `exempt` from the daily message limit (`messaging.send(...,
  exempt=True)`, kind `"<kind>-review"`): like the weekly check-in they're expected,
  and storing one that the limit then held back would show on the web a review
  never sent. The row is claimed (`INSERT OR IGNORE` on the unique `key`) before
  sending; no `once_keys` row.
- `reviews.phase_row_id` has no foreign key (as `phase_end_requests`): an erased
  phase's review stays.
- Week: `reviews` lists those sent on the week's dates (start..end, by the local
  date of `created_at`), each `{id, kind, title, period_start, period_end, text,
  sent_at}`. The page shows each as a collapsed card like the weekly report (title
  left, the period it covers right), above the report.
- Measurements: `body_fat` (read-only list; no web command, the user gives their
  own in chat, ticket 04). The page shows a "Body fat" card between Waist and
  Progress photos: date, %, and "From the photos" / "Your estimate · photos said
  x %". The Setup summary line is unchanged.
