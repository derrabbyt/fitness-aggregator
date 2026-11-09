# 07: Weekly check-in: facts, verdict, report

**What to build:** At the user's check-in time, code computes the weekly facts for the week that just ended, the decision model turns them into a verdict, the verdict is stored with its facts, and the weekly report goes out. Lift progression isn't computed yet, so progression is not evaluated and only the "gaining too fast" scenario could lead to a proposal (proposals themselves come in ticket 09; here the verdict only records them).

**Blocked by:** 05 (Phase start: reverse)

**Status:** ready-for-agent

- [ ] The weekly job runs at the configured check-in day and time, once per week
- [ ] Weekly facts are computed in code and validate against the weekly-facts schema: 7-day averages, weekly rate, weigh-in count, logging completeness, weekly intake vs target, daily targets with counted activity, maintenance estimate (back-calculated, ≥ 3 weeks, glycogen weeks excluded), phase week, glycogen window, gain band and `vs_band`, carb remainder, predicted weight and prediction miss, data freshness, context notes for the week, and verdict history
- [ ] Prediction miss uses a new fixed core param (0.3 kg) instead of the band width; schema, README and skills are updated and the validator stays green
- [ ] The decision model (`COACH_DECISION_MODEL`, default `claude-opus-5-5`) returns a verdict validated against the weekly-verdict schema; an invalid verdict is not acted on and the user is told the check-in failed
- [ ] The verdict is stored with the facts it was based on and its rule ids
- [ ] A week with a `sport_load` context note is skipped for confirmation (neither counts nor breaks), and no "raise calories" or "training needs a look" comes from it; the weekly-decision skill and the coach-skills README are updated from "resets" to "skipped"
- [ ] Unusable weeks, glycogen-window weeks and adherence-gate weeks are skipped for confirmation as specified
- [ ] The weekly-report skill writes the report from facts and verdict: decision in plain words, weight, food, training (progression not evaluated yet), activity if relevant, deferred items, what's due next week, questions
- [ ] Tests feed synced data through the fake api client and a scripted verdict, and check the facts handed to the model (schema-valid, the right numbers for weight, intake, adherence, prediction miss, skipped weeks) and the report in the outbox
