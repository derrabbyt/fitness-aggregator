# 03: Context notes and profile in chat

**What to build:** The first model call. A free-text message in the coach chat goes to the model with the coach-core skill as the cached prefix and the coach-chat and context-log skills as the task. Context in any form (sick since Tuesday, travel this weekend, wrestling camp, started creatine) is stored as a context note with dates and tags and confirmed in one line. Telling the coach a preference updates the coach profile, which `/profile` shows. Out-of-scope topics get a one-line decline.

**Blocked by:** 01 (Coach service skeleton)

**Status:** ready-for-agent

- [ ] The model client wraps the Anthropic SDK, reads `COACH_ANTHROPIC_BASE_URL` / `COACH_ANTHROPIC_API_KEY` with fallback to `ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY`, and uses `COACH_MODEL` (default `claude-sonnet-5-5`)
- [ ] Prompts use a cached prefix (coach-core, active phase skill if any, tool definitions), then the task skill, a short state snapshot and the input; chat keeps only a short history
- [ ] `add_context_note` stores the user's text unchanged with `applies_from` / `applies_to`, tags (including `sport_load` for a heavy week), optional exercise id and `suggest_unusable`; the reply confirms in one line
- [ ] `update_coach_profile` and `get_coach_profile` work; `/profile` shows the stored profile
- [ ] Medical, PED, supplement, technique and meal-tip questions get a one-line decline
- [ ] The coach writes in English
- [ ] The skills package reflects that sport load is a context-note tag: `set_week_sport_load` is removed from the tools doc and the coach-chat and context-log skills; the validator stays green
- [ ] Tests with a scripted fake model cover storing a note, a profile change, and that tool calls are executed by code
