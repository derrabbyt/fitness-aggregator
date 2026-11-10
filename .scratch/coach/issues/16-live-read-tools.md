# 16: Live read-only MFP and Hevy tools for the coach model

**What to build:** In chat (and the other model tasks that already get tools), the coach model can read MyFitnessPal and Hevy live through the api's MCP tools endpoint (:8001), so it can answer things the synced daily totals can't ("what did I eat Tuesday?", "which entry looks like a typo?", "what did I do on pull-ups last week?"). Reading only: no write tool is ever offered. Requested by the user on 2026-11-10.

**Blocked by:** 03 (model tool loop), 10 (chat about the plan)

**Status:** ready-for-agent

- [ ] A read-only allowlist in coach code, e.g. `MFP_READ_TOOLS = {fitness_get_day, fitness_get_activity, fitness_get_exercise, fitness_get_exercise_entries, fitness_get_note, fitness_get_trends, fitness_search_food}` and all Hevy read tools (`hevy_get_account`, `hevy_list_workouts`, `hevy_get_workout`). Left out on purpose: every write (`fitness_log_*`, `fitness_delete_*`, `fitness_modify_food`, `fitness_quick_add`, `fitness_clear_food_pin`, `fitness_set_goal`), `fitness_draft_food` (the coach doesn't log food) and `fitness_bulk_export` (huge output; the synced data covers it)
- [ ] Tool definitions come from the api's `tools/list` (filtered by the allowlist) so schemas stay in sync, fetched once at start-up and cached; if the api is down at start-up the coach runs without live tools and retries the listing later. Calls go through the coach's api client to `fa-api` only (one MFP session owner); read calls may be retried, writes are never reachable
- [ ] Live tools are registered for chat (coach-chat) and any other task the registry already gives tools; results are truncated to a sane size before going back to the model
- [ ] Skills (coach-core / coach-chat) and TOOLS.md say: live reads are for looking things up and explaining; targets, guardrails and weekly decisions still come from code-computed facts and stored verdicts; odd entries are pointed out for the user to fix in MFP, never changed
- [ ] Tests with a fake api client: the model's tool list contains the allowed live tools and no write tool (checked by name and by pattern, like the food bot's test, including `fitness_set_goal`); a scripted chat call to `fitness_get_day` returns through the tool loop; the coach starts without live tools when listing fails
- [ ] README and CLAUDE.md mention the coach's live read tools and that its allowlist must stay read-only
