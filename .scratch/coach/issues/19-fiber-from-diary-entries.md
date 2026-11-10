# 19: Fiber from diary entries

**What to build:** The user logs fiber (Ballaststoffe) normally in MFP, but the sync endpoint returns `fiber_g: null` because it reads the diary totals view, which carries only the visible columns (kcal, protein, carbs, fat), and a free account can't add a Fiber column. Sum fiber from the per-entry diary data instead (MFP's `/v2/diary` food entries carry `nutritional_contents`, which normally include fiber), so the fiber flag in the weekly report can work.

**Blocked by:** 02

**Status:** resolved

- [x] `/api/sync/mfp` fills `food.fiber_g` with the day's sum of fiber over food entries (from the same `/v2/diary` read the endpoint already does; no extra MFP request), or null when no entry has a fiber value. Find the field name and units in the library sources (`/tmp/claude-1000/-home-debian-projects-fitness-aggregator/b78f9df1-d31b-4728-a922-f644ddfbd08f/scratchpad/libsrc/`, NOTES.md) and code defensively (missing key → ignored; all missing → null)
- [x] The coach stores and uses it unchanged (it already handles `fiber_g`); README "Sync endpoints" updated
- [x] An offline check with a fake MFP diary payload (with and without fiber) confirms the sum; the orchestrator verifies the field against the live diary once (ticket comments)

## Comments

- Field: `nutritional_contents.fiber` on each `/v2/diary` item, grams (the library's `/v2/foods` reader and `DEFAULT_MEASURE_AND_UNIT["fiber"] = g`; the diary is assumed to carry it already scaled to the logged amount, like `nutritional_contents` in our Quick Add). `_fiber_g` in `api.py` sums every item that has it, whatever its `type` (food entries, quick adds; exercise/steps have no `nutritional_contents`). Accepted: a number, or `{"value", "unit"}` with unit g/grams/none; missing, null, strings, other units are skipped; none at all → null; 0 counts as 0. Rounded to 0.1 g. A day with no diary entries keeps `fiber_g` null like the other totals. A Fiber column on the diary page stays as the fallback when no entry has fiber. No extra MFP request (`items` from the existing read is passed to `_sync_food`).
- Offline check (not in the test run; the api has no test harness): `scratchpad/fiber19/check.py` mounted into `fitness-aggregator:coach-19` and run with `docker run --rm --network none`. It replaces `mfp_server.with_session` with a fake client (fake `session.get` for `/v2/diary`, `get_date`, `get_measurements`) and `api_headers`, then calls `sync_mfp` for 4 days: fiber 4.2 + `{"value": 3.1, "unit": "g"}` + entries without fiber → 7.3; entries with no/junk fiber → null; no entries → null; fiber 0 → 0.0; exactly one `/v2/diary` GET per day; steps and exercises unchanged. Passed.
- Open (orchestrator): check once against the live diary that food entries carry `nutritional_contents.fiber` in grams for the logged amount (e.g. `/api/sync/mfp?start=<a day with fiber logged>` vs the MFP app's day total). Third box left unticked for that.
- Not touched (outside this ticket's files): the comment in `coach/src/fa_coach/migrations/02_sync.sql` still says fiber is null without a Fiber column.
- **Live check (2026-11-10, orchestrator):** `/api/sync/mfp` for 2026-11-07..10 returned `fiber_g` 22.6, 16.2, 11.4 and 0.0 (today, 3 entries so far); the field is present in the live diary entries.
