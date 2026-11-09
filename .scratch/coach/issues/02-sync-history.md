# 02: Sync history from MFP and Hevy

**What to build:** The coach fills its database from the api: food totals, weight, steps and runs from MyFitnessPal, and lifting sessions with per-set load and reps from Hevy. The first sync loads 16 weeks of history; after that it syncs several times a day and on demand. Weigh-in outliers are marked silently, the time of the last successful sync is recorded, and stale data produces one notice. `/sync` runs a sync and reports what came in.

**Blocked by:** 01 (Coach service skeleton)

**Status:** ready-for-agent

- [ ] The api has REST read endpoints returning compact per-day records for a date range: food totals (kcal, protein, carbs, fat, fiber; produce grams if derivable, else null) and whether the day is logged, weight, steps, runs (kcal, distance, duration); and Hevy sessions with exercise id, title and per-set load and reps
- [ ] The api reads Hevy in pages of 5 and reaches MFP only through its existing session; nothing new talks to MFP directly
- [ ] The api endpoints are checked once by hand against live MFP and Hevy (noted in the ticket's comments)
- [ ] The first `sync` loads 16 weeks; later syncs fetch only what's new or changed (recent days are re-read so late edits land)
- [ ] A scheduler loop calls `sync` several times a day; `/sync` triggers it and replies with days and sessions synced and the last sync time
- [ ] Weigh-in outliers are marked in code and excluded from trend inputs, without a message
- [ ] When the last successful sync is older than the stale limit (params), the coach sends one notice and the freshness is available to later facts
- [ ] Tests through the `Coach` seam with a fake api client cover first sync, incremental sync, outlier marking and the stale notice
