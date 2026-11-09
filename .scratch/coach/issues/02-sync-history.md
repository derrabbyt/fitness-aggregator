# 02: Sync history from MFP and Hevy

**What to build:** The coach fills its database from the api: food totals, weight, steps and runs from MyFitnessPal, and lifting sessions with per-set load and reps from Hevy. The first sync loads 16 weeks of history; after that it syncs several times a day and on demand. Weigh-in outliers are marked silently, the time of the last successful sync is recorded, and stale data produces one notice. `/sync` runs a sync and reports what came in.

**Blocked by:** 01 (Coach service skeleton)

**Status:** ready-for-agent

- [x] The api has REST read endpoints returning compact per-day records for a date range: food totals (kcal, protein, carbs, fat, fiber; produce grams if derivable, else null) and whether the day is logged, weight, steps, runs (kcal, distance, duration); and Hevy sessions with exercise id, title and per-set load and reps
- [x] The api reads Hevy in pages of 5 and reaches MFP only through its existing session; nothing new talks to MFP directly
- [ ] The api endpoints are checked once by hand against live MFP and Hevy (noted in the ticket's comments)
- [x] The first `sync` loads 16 weeks; later syncs fetch only what's new or changed (recent days are re-read so late edits land)
- [x] A scheduler loop calls `sync` several times a day; `/sync` triggers it and replies with days and sessions synced and the last sync time
- [x] Weigh-in outliers are marked in code and excluded from trend inputs, without a message
- [x] When the last successful sync is older than the stale limit (params), the coach sends one notice and the freshness is available to later facts
- [x] Tests through the `Coach` seam with a fake api client cover first sync, incremental sync, outlier marking and the stale notice

## Comments

- **Endpoints:** `GET /api/sync/mfp?start=&end=` (≤ 31 days) and `GET /api/sync/hevy?start=&end=` (≤ 400 days), shapes in README ("Sync endpoints"). The coach asks MFP in 4-week chunks. MFP is read per day with `client.get_date` (totals, `complete`, entry count) plus `/v2/diary` (steps, exercise entries), weights once per request with `get_measurements("Weight")`, all inside `with_session`. A day that fails has `error` set and is skipped by the coach (reported by `/sync`); an auth/session error fails the whole request so the headless refresh isn't tried once per day.
- **"Logged"** (coach side, `history.days`): any food entry, or the day marked complete in MFP. `complete` is kept separately for the facts tickets.
- **Runs:** the api returns every MFP exercise entry with `run` = name matches run/jog; the coach keeps all of them (`exercises`) and exposes `runs` for the counted-activity work.
- **Produce grams:** always null (nothing in MFP to derive it from).
- **Outliers:** new core params `data.weight_outlier_kg` (1.5) and `data.weight_outlier_window_days` (3), listed as assumptions in the coach-skills README: a weigh-in more than 1.5 kg from the median of the other weigh-ins within 3 days either side (at least two) is an outlier. Recomputed over all weigh-ins on every MFP sync.
- **Freshness:** last successful sync = the older of the MFP and Hevy successes (`features.sync.freshness`, `history.freshness`). Stale notice: once per stale stretch (keyed by that time), never before the first sync attempt.
- **Scheduler:** unchanged from ticket 01 (sync on start, then every 4 h).
- **Unverified field names (hand check pending):** MFP `fiber` total (only with a Fiber diary column), the Strava `source` string and run names; Hevy `exercise_template_id`, `exercise_type`, set `indicator` values. All pass through as null when absent.
- **Hand check against live MFP and Hevy:** not done by the implementer (left to the orchestrator).
