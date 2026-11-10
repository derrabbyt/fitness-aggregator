# 17: MFP goal is base + surplus; counting and counter decisions

**What to build:** Decisions the user made on 2026-11-10 after the code review. MFP is only a logging tool; the real daily targets live in the coach.

**Blocked by:** code-review fixes (`coach/review-fixes`), 16

**Status:** ready-for-agent

- [ ] **MFP goal = base maintenance + surplus** (the rest-day target; ticket 18 refines this to base at average steps + surplus), not the average daily target. Activity (runs, lifting, wrestling, extra sessions) stays on top: exact in the coach's daily targets, mentally in MFP. Macros for the MFP goal are computed at that kcal (protein and fat in g/kg as usual, carbs the remainder). Applies to phase confirm, approved calorie proposals and approved calibration changes. The phase-start preview and approval cards say what MFP will show and that activity comes on top. Update spec (`.scratch/coach/spec.md`: stories 29 and 54, "fa-api additions", "Facts, rules and guardrails"), root `SPEC.md`, ADR 0001's consequence line if it says "average", skills (phase-start, weekly-report, coach-chat, TOOLS.md), README and tests.
- [ ] **Calibration changes keep the measured maintenance:** base = maintenance estimate − average counted activity with the new values, so base moves and the average stays. Because base changes, the MFP goal (base + surplus) changes: set it once through `mfp_goal.set_once`, read back once, never retried (ticket 10 currently skips the write when the average is unchanged).
- [ ] **Planned wrestling counts only from the phase start.** On days before the active phase started (the maintenance back-calculation and preview windows), only synced activity counts (Strava runs, Hevy lifting) and reported sessions; planned-but-unreported sessions don't. From the phase start on, wrestling counts as planned unless reported skipped.
- [ ] **Free-account macro rounding:** the user has no MFP premium, so MFP may store macros as a percentage split in 5 % steps. The goal write counts as set when calories match (±1 kcal) and each macro is within MFP's 5 %-of-calories rounding; the confirmation then says MFP shows rounded macros and the exact grams are in the coach. A calorie mismatch is still "not set".
- [ ] A bare-number counter keeps the proposal's sign (already the behaviour from ticket 10; keep a test for it).
- [ ] Tests cover the MFP goal value on confirm, approve and calibration, the calibration write, wrestling before vs after the phase start, and macro rounding accepted vs a calorie mismatch.
