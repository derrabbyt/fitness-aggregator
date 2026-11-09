# 08: Lift progression in the weekly decision

**What to build:** Weekly facts now include gym progression, so the full A–E table applies. Each tracked lift is compared with the best of its last 3 sessions, using its own sessions whenever they happened. Stalls, the deload signal, new baselines and paused exercises are computed in code.

**Blocked by:** 07 (Weekly check-in: facts, verdict, report)

**Status:** ready-for-agent

- [ ] Per tracked lift: status improved / same / declined / new baseline / paused vs the best of up to 3 previous sessions (at least 2 needed), counted only if trained within the recency window
- [ ] Progress = more load or reps at the same execution; micro-progressions count; for dips, pull-ups and similar, bodyweight gained counts as added load (effective load)
- [ ] `progression_met` is true when at least the configured share of counted lifts improved, null when no lift could be counted
- [ ] No-progress streaks, stalls (3 sessions without progress), the deload signal (2+ lifts declining over 2+ sessions), possible resets (load drop of 15%+), session volume and PRs are computed
- [ ] Baseline resets and pauses stored by later tickets are respected (a reset starts a new baseline; a paused exercise isn't judged)
- [ ] The weekly report's training section shows how many tracked lifts improved, PRs, stalls and deload signals
- [ ] Tests cover improvement, same, decline, a bodyweight lift, a lift not trained within the window, a stall, a deload signal, and A–E outcomes B, C and D end to end with a scripted verdict
