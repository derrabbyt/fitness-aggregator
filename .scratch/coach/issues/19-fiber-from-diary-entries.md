# 19: Fiber from diary entries

**What to build:** The user logs fiber (Ballaststoffe) normally in MFP, but the sync endpoint returns `fiber_g: null` because it reads the diary totals view, which carries only the visible columns (kcal, protein, carbs, fat), and a free account can't add a Fiber column. Sum fiber from the per-entry diary data instead (MFP's `/v2/diary` food entries carry `nutritional_contents`, which normally include fiber), so the fiber flag in the weekly report can work.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] `/api/sync/mfp` fills `food.fiber_g` with the day's sum of fiber over food entries (from the same `/v2/diary` read the endpoint already does; no extra MFP request), or null when no entry has a fiber value. Find the field name and units in the library sources (`/tmp/claude-1000/-home-debian-projects-fitness-aggregator/b78f9df1-d31b-4728-a922-f644ddfbd08f/scratchpad/libsrc/`, NOTES.md) and code defensively (missing key → ignored; all missing → null)
- [ ] The coach stores and uses it unchanged (it already handles `fiber_g`); README "Sync endpoints" updated
- [ ] An offline check with a fake MFP diary payload (with and without fiber) confirms the sum; the orchestrator verifies the field against the live diary once (ticket comments)
