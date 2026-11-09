# 06: MFP goal set on phase confirm

**What to build:** Confirming a phase sets the user's MFP goal to the new average daily target and macros. The api gets a write tool for this that only coach code calls: once, read back once, never retried. The food bot and the coach model never see it.

**Blocked by:** 05 (Phase start: reverse)

**Status:** ready-for-agent

- [x] The api's tools endpoint has `fitness_set_goal` (calories, protein, carbs, fat) that sets the MFP nutrition goal and returns the stored goal
- [x] `fitness_set_goal` is not in the food bot's read-tool allowlist and is never offered to the coach model
- [x] On phase confirm, coach code calls it once, then reads the goal back and reports in the confirmation message whether MFP now shows the new goal
- [x] A failed or uncertain write is reported to the user and not retried; the phase stays active and the coach targets stay as confirmed
- [ ] Checked once by hand against live MFP (noted in the ticket's comments)
- [x] Tests with the fake api client cover a successful write, a failed write that isn't retried, and that a second confirm tap doesn't write again

## Comments

- **Not the library's `set_new_goal`** (spec said "the MFP library's goal-setting call"): `src/fitness_aggregator/mfp_goal.py` makes the same request itself (GET `v2/nutrient-goals`, POST the item with new energy/macros in the default and every weekday goal, valid from today), because `set_new_goal` would have to run inside mfp-mcp's `with_session`, whose `run_with_refresh` re-runs the operation after any auth-looking error (a 401/403 POST included), i.e. could send the write twice. Reads go through `with_session`; the one POST goes out via `asyncio.to_thread` outside it. Also avoids `set_new_goal` mutating `client.session.headers` and raising calories to the macro sum silently (the tool refuses macros > calories + 25 instead). Calories are always sent as `calories` (kcal) unit.
- **Added `fitness_get_goal(date?)`** (read, `READS_MFP`) for the coach's read-back; also handy by hand. `fitness_set_goal` is annotated `CHANGES_MFP` (not idempotent), not `SETS_IN_MFP`, so no client treats it as safe to resend.
- **Write outcomes** (api): `sent` / `rejected` (MFP error status) / `uncertain` (no answer from MFP) / `not_sent` (no session). Coach status (`fa_coach/mfp_goal.py`): `set` if the read-back matches within 1 kcal/g; `not_set` if the write was answered but MFP shows something else; `uncertain` if nothing could be read back, or the coach got no reply from the api and MFP doesn't show the goal yet (it may still land). Each is one line on the confirmation card; never retried.
- **Coach→api call is one raw JSON-RPC `tools/call` POST** (httpx, `retries=0`, stateless endpoint, no MCP session/initialize), so no client layer can resend it.
- **Reusable for ticket 09:** `mfp_goal.set_once(coach, key, goal, now)` claims `key` in a new table `mfp_goal_writes` (migration `06_mfp_goal.sql`) before sending, so the same key never writes twice (double taps, restarts); a row left at `sending` after a crash is never resent. Returns None for an already-used key; `mfp_goal.describe(result)` gives the user line. Phase confirm uses key `phase-start:<phase row id>`.
- **Confirm hooks may now return a line** (`phases.ConfirmHook` → `str | None`); `confirm_phase_start` edits the card a second time with those lines after "✅ Started". `test_full_start_previews_then_confirms_once` now allows that second edit.
- Bot test `test_model_gets_no_write_tools` now also rejects `set_`, `quick_add`, `add_` and anything with `goal`, and asserts `fitness_set_goal` explicitly.
- **Hand check (open, for the orchestrator):** with the api running, `docker compose exec api python scripts/mcp_call.py mfp '[["fitness_get_goal", {}]]'`, then once `'[["fitness_set_goal", {"calories": ..., "protein": ..., "carbs": ..., "fat": ...}]]'` and check `write`/`stored`/`matches` and the MFP website (per-weekday goals are overwritten; on a non-premium account MFP may round macros, which the coach would then report as "not set" with what MFP shows). Verified offline only: against a fake MFP client, 200 → 1 POST, `sent`, stored matches; 401/403 → 1 POST, no session refresh, `rejected`; connection error → 1 POST, `uncertain`; coach `HttpApiClient` → real tools app over loopback round-trips both tools.
