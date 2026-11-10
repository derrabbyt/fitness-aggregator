# 13: Waist and photo check-ins

**What to build:** Every two weeks the coach asks for the waist measurement and, when photos are on, a photo set, with the photo protocol reminder. What the user sends is stored with its date and acknowledged. Photo review (body-fat estimates) comes later; this ticket makes sure the first sets aren't lost.

**Blocked by:** 05 (Phase start: reverse)

**Status:** resolved

- [x] Waist and photo due dates are computed in code from the measurement params and the phase start; reminders are sent once when due (photos only when photos are enabled)
- [x] The photo prompt includes the protocol: same spot and light, camera at hip height, morning, fasted, unpumped, same poses
- [x] Photos sent to the coach chat are stored as a dated photo set in the coach's state directory; waist values are stored with their date
- [x] The weekly report's "due next week" includes waist and photos per the due dates
- [x] Switching photos off (in chat) stops photo reminders and nothing else changes
- [x] Tests cover due dates, a reminder sent once, storing a photo set and a waist value, and photos off

## Comments

- Code: `coach/src/fa_coach/features/measurements.py`, table `migrations/13_measurements.sql`,
  tests `coach/tests/test_measurements.py`. `Coach.state_dir` (the database's folder, i.e.
  `state/coach`; the test's tmp dir) holds photos as `photos/<date>/<n>.jpg`.
- For ticket 07: `measurements.measurements_due(coach, start, end)` returns
  `[{"date", "kind": "waist"|"photos"}]` for the range (photos only while on; empty without an
  active phase). The weekly report box stays open until 07 uses it.
- Decided (not in the spec): photos are also due on the phase start date (the baseline set
  later reviews compare against); the waist isn't, since `waist_cm_start` is a setup value.
  Reminders go out from 07:00 on the due date (`REMINDER_TIME`, an assumption), one message for
  everything due, once per due date; if the coach was down it is sent late (still once) for the
  latest due date only, and not at all if the value already came in on or after the due date.
- Waist input is code-only: "waist 84.5", a sentence with "waist" and one plausible number
  (40-200 cm), or a bare number while a waist reminder is open. Questions go to the chat.
  Photos are stored whenever they arrive (also with photos off or no phase), one set per day.
- Reminders count toward `max_unprompted_messages_per_day` through ticket 11's shared counter
  (`messaging.send`). At the limit nothing is claimed, so the reminder goes out on a later day
  (still once per due date). Reminders now go out only from 07:00 (`REMINDER_TIME`), also late
  ones, so a held-back reminder isn't sent right after midnight (test
  `test_reminders_count_toward_the_daily_message_limit`).
