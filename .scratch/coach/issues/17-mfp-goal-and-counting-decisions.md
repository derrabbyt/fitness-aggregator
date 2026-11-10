# 17: MFP goal is base + surplus; counting and counter decisions

**What to build:** Decisions the user made on 2026-11-10 after the code review. MFP is only a logging tool; the real daily targets live in the coach.

**Blocked by:** code-review fixes (`coach/review-fixes`), 16

**Status:** resolved

- [x] **MFP goal = base maintenance + surplus** (the rest-day target; ticket 18 refines this to base at average steps + surplus), not the average daily target. Activity (runs, lifting, wrestling, extra sessions) stays on top: exact in the coach's daily targets, mentally in MFP. Macros for the MFP goal are computed at that kcal (protein and fat in g/kg as usual, carbs the remainder). Applies to phase confirm, approved calorie proposals and approved calibration changes. The phase-start preview and approval cards say what MFP will show and that activity comes on top. Update spec (`.scratch/coach/spec.md`: stories 29 and 54, "fa-api additions", "Facts, rules and guardrails"), root `SPEC.md`, ADR 0001's consequence line if it says "average", skills (phase-start, weekly-report, coach-chat, TOOLS.md), README and tests.
- [x] **Calibration changes keep the measured maintenance:** base = maintenance estimate − average counted activity with the new values, so base moves and the average stays. Because base changes, the MFP goal (base + surplus) changes: set it once through `mfp_goal.set_once`, read back once, never retried (ticket 10 currently skips the write when the average is unchanged).
- [x] **Planned wrestling counts only from the phase start.** On days before the active phase started (the maintenance back-calculation and preview windows), only synced activity counts (Strava runs, Hevy lifting) and reported sessions; planned-but-unreported sessions don't. From the phase start on, wrestling counts as planned unless reported skipped.
- [x] **Free-account macro rounding:** the user has no MFP premium, so MFP may store macros as a percentage split in 5 % steps. The goal write counts as set when calories match (±1 kcal) and each macro is within MFP's 5 %-of-calories rounding; the confirmation then says MFP shows rounded macros and the exact grams are in the coach. A calorie mismatch is still "not set".
- [x] A bare-number counter keeps the proposal's sign (already the behaviour from ticket 10; keep a test for it).
- [x] Tests cover the MFP goal value on confirm, approve and calibration, the calibration write, wrestling before vs after the phase start, and macro rounding accepted vs a calorie mismatch.

## Comments

- **Worked example moved.** With planned wrestling not counting before the phase start, the tests' preview window has no counted activity: base 2536, surplus -236, rest day 2300 (= the MFP goal), lifting 2600, wrestling 2900. Weekly fixtures eat 2300 a day (was 2200) so week 3 stays within the adherence tolerance (16,100 vs 16,700, -3.6 %).
- **Calibration window unchanged:** base moves by what the new values change over the last 28 days (as ticket 10), i.e. base = maintenance - (old average activity + that shift). The MFP goal is written when its kcal (base + surplus) changed; with `maintenance_includes_activity: false` base doesn't move, so nothing is written.
- **Macro rounding tolerance:** each macro within 5 % of the calories (a full 5 % step, not half), counted as `set` with `macros_rounded`; only when the api says the write was `sent` (or, after a lost reply, from the coach's own read-back). A rejected write is still `not_set`.
- **Cards:** the proposal card (and the code-written report line) says what MFP will show (`proposals.mfp_goal_after`), and the approval summary says it again.
- `counted_activity_on(..., planned_from=...)`: default the active phase's start; no active phase counts no planned wrestling. The preview passes the new start (today).
