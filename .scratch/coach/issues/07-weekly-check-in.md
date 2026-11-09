# 07: Weekly check-in: facts, verdict, report

**What to build:** At the user's check-in time, code computes the weekly facts for the week that just ended, the decision model turns them into a verdict, the verdict is stored with its facts, and the weekly report goes out. Lift progression isn't computed yet, so progression is not evaluated and only the "gaining too fast" scenario could lead to a proposal (proposals themselves come in ticket 09; here the verdict only records them).

**Blocked by:** 05 (Phase start: reverse)

**Status:** ready-for-agent

- [x] The weekly job runs at the configured check-in day and time, once per week
- [x] Weekly facts are computed in code and validate against the weekly-facts schema: 7-day averages, weekly rate, weigh-in count, logging completeness, weekly intake vs target, daily targets with counted activity, maintenance estimate (back-calculated, ≥ 3 weeks, glycogen weeks excluded), phase week, glycogen window, gain band and `vs_band`, carb remainder, predicted weight and prediction miss, data freshness, context notes for the week, and verdict history
- [x] Prediction miss uses a new fixed core param (0.3 kg) instead of the band width; schema, README and skills are updated and the validator stays green
- [x] The decision model (`COACH_DECISION_MODEL`, default `claude-opus-5-5`) returns a verdict validated against the weekly-verdict schema; an invalid verdict is not acted on and the user is told the check-in failed
- [x] The verdict is stored with the facts it was based on and its rule ids
- [x] A week with a `sport_load` context note is skipped for confirmation (neither counts nor breaks), and no "raise calories" or "training needs a look" comes from it; the weekly-decision skill and the coach-skills README are updated from "resets" to "skipped"
- [x] Unusable weeks, glycogen-window weeks and adherence-gate weeks are skipped for confirmation as specified
- [x] The weekly-report skill writes the report from facts and verdict: decision in plain words, weight, food, training (progression not evaluated yet), activity if relevant, deferred items, what's due next week, questions
- [x] Tests feed synced data through the fake api client and a scripted verdict, and check the facts handed to the model (schema-valid, the right numbers for weight, intake, adherence, prediction miss, skipped weeks) and the report in the outbox

## Comments

- Code: `fa_coach/weekly_facts.py` (`compute(coach, end, now)`; `facts_hooks` for ticket 08's
  `training`, ticket 09's `history.open_proposals` / `last_rejected`), `fa_coach/weekdata.py`
  (per-day intake vs targets, `intake_summary`, steps; shareable with the daily facts),
  `features/weekly_checkin.py` (job, `/checkin`, code rules on the verdict, storage, report;
  `report_hooks` for ticket 09's `proposal_result` / `changes_applied`; `stored(coach, iso_week)`),
  table `migrations/07_weekly.sql`, tests `coach/tests/test_weekly_checkin.py`.
- **Which week:** the 7 days ending the day before the check-in day (a Monday 09:00 check-in
  judges Mon–Sun; a Sunday 18:00 one judges Sun–Sat, so Sunday's food is never half logged).
  `iso_week` is the ISO week of the last day. A check-in whose week starts before the phase
  start sends one line saying when the first one comes; check-in moments up to the phase
  confirmation are ignored.
- **Day logged:** MFP has no "partial" signal, so a day is `complete` when any food is logged
  (or the day marked complete), else `missing`.
- **Prediction:** at the start of the week, `prev_avg_7d_kg + surplus x 7 / kcal_per_kg` (the
  targets assume the maintenance estimate). Miss = error above `decisions.prediction_miss_kg`
  (0.3, new core param).
- **Confirmation counted in code:** each stored verdict records `counts_for_confirmation` and
  `skip_reason` (unusable, glycogen_window, adherence_gate, sport_load); facts carry
  `history.confirmation_streaks` (earlier weeks since the last change, skipped weeks left out),
  so the model only adds this week. Ticket 09's confirmation guardrail can reuse
  `weekly_facts.confirmation_streaks`.
- **Sport load in code too:** for a week with a `sport_load` note code turns an increase into
  hold, drops an increase proposal and the `training_needs_look` flag, sets
  `sport_load_applied`, adds `sport_load_week` and `WD-SPORT` (recorded in `code_adjustments`).
  Any week skipped for confirmation carries no proposal. Facts: `activity.sport_load_note_ids`
  replaces `sport_load_source`.
- **Schema changes:** `data_quality.last_sync_at` nullable; `history.last_change` gets `source`
  (`proposal_id` null for the phase start); `previous_verdicts[]` get `counts_for_confirmation`
  and `skip_reason`; `history.confirmation_streaks`. The report's `due` is the list from
  `measurements.measurements_due` for the 7 days from the check-in day; `deferred` is `[{date, text}]` from ticket 11's
  `messaging.deferred` for the week's days.
- **Sending:** every check-in message (report, failure, "first check-in comes …") goes through
  `messaging.send(..., exempt=True)`: the daily message limit never holds it back.
- **Failures:** an invalid verdict (schema, or wrong week/phase) or an unreachable model stores
  a failed attempt and tells the user; `/checkin` runs it again. If the report model fails,
  code sends a short fallback report from the verdict's reasoning and the numbers.
- `maintenance_estimate.excluded_weeks` lists the weeks between the estimate's window and this
  week (left out as glycogen or unusable weeks); `base_kcal` takes the window's average
  counted activity off the back-calculated value.
