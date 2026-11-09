# 14: Estimated kcal for reported sessions

**What to build:** When the user reports an extra or unsynced session in chat, giving kcal is optional. "Played football for 90 minutes" or "ran 5 k, no watch" is enough: the model extracts the activity type and duration (asking once if the duration is missing), and code estimates the kcal. A number the user gives always wins. The confirmation line shows the kcal counted and whether it was estimated, so the user can correct it.

**Blocked by:** 04 (Training plan in chat)

**Status:** ready-for-agent

- [ ] `set_session_status` (extra, and done for a planned session without synced data) takes either `kcal` or `activity` + `duration_min`; it never takes a model-computed number
- [ ] Code estimates kcal = MET × current 7-day trend weight (kg) × hours, with a MET table per activity type in core params (schema, params, README assumption row; the validator stays green); an unknown activity type gets a generic moderate MET and the reply says so
- [ ] Wrestling and lifting without a kcal still use their setup values per session; runs without Strava are estimated from duration and get the run discount like synced runs
- [ ] The stored session records its kcal source (`reported` or `estimated`) and the inputs, and counted activity uses it
- [ ] With no trend weight yet, nothing is guessed: the coach asks for kcal instead
- [ ] coach-chat / context-log skills and TOOLS.md describe this: extract type and duration, ask once for a missing duration, never compute kcal
- [ ] Tests cover an estimated extra session, a reported kcal winning over the estimate, an unknown activity type, a missing duration (model asks), and no trend weight
