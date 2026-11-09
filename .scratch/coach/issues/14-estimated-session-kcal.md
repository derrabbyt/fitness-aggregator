# 14: Estimated kcal for reported sessions

**What to build:** When the user reports an extra or unsynced session in chat, giving kcal is optional. "Played football for 90 minutes" or "ran 5 k, no watch" is enough: the model extracts the activity type and duration (asking once if the duration is missing, or passing it when the description makes it obvious), and code estimates the kcal. When code can't estimate (unknown activity type, no trend weight yet, other missing inputs), the model may pass its own estimate instead of asking. A number the user gives always wins. The confirmation line shows the kcal counted and whether they were the user's, code's estimate or the model's estimate, so the user can correct it.

**Blocked by:** 04 (Training plan in chat)

**Status:** ready-for-agent

- [x] `set_session_status` (extra, and done for a planned session without synced data) takes `kcal` (the user's number), or `activity` + `duration_min` for code's estimate, or the model's own `kcal_estimate` only when code can't estimate
- [x] Code estimates kcal = MET × current 7-day trend weight (kg) × hours as the first choice, with a MET table per activity type in core params (schema, params, README assumption row; the validator stays green)
- [x] When code can't estimate (unknown activity type, no trend weight yet, or other missing inputs), the model's `kcal_estimate` is stored with kcal source `model_estimate` and the reply says it's the model's estimate; without one the tool tells the model to estimate or ask
- [x] Wrestling and lifting without a kcal still use their setup values per session; runs without Strava are estimated from duration and get the run discount like synced runs
- [x] The stored session records its kcal source (`reported`, `estimated` or `model_estimate`) and the inputs, and counted activity uses it
- [x] coach-chat / context-log skills and TOOLS.md describe this: extract type and duration, ask once for a missing duration (or pass it when obvious), the user's number wins, the model's own estimate only when code can't
- [x] Tests cover an estimated extra session, a reported kcal winning over the estimate, a model-estimated session (unknown type, and no trend weight), and a missing duration (model asks)

## Comments

- Changed during implementation at the user's request: the model may estimate kcal when code can't (source `model_estimate`); the generic moderate MET fallback and "no trend weight → ask for kcal" were dropped.
- Code's estimate wins over a `kcal_estimate` the model passes when code can estimate.
- "Current" trend weight = mean of the non-outlier weigh-ins in the 7 days ending today (`history.trend_weight_kg`), rounded to 0.1 kg; the estimate is rounded to whole kcal and stored, so later weigh-ins don't change it.
- MET table (assumption, conservative Compendium-style "general" values): running 8.0, cycling 7.5, swimming 6.0, football 7.0, basketball 6.5, tennis 7.0, hiking 6.0, walking 3.5, rowing 6.0, martial_arts 6.0. `martial_arts` is for other combat sports (BJJ, boxing, …) reported as type `other`; wrestling sessions use the wrestling setup value.
- A planned run marked done with no kcal and no duration is still accepted (it counts only if Strava syncs it), as before.
- The tool result carries `reported` {kcal, kcal_source, kcal_counted, say}; `kcal_counted` is null while a needed setup value (run discount, wrestling/lifting kcal) isn't set yet.
