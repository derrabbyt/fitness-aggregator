# 08: Live reads in phase start

**What to build:** The phase-start task gets the `live` tool source (the read-only `READ_TOOLS` allowlist, unchanged). The phase-start skill says live reads are for looking things up; setup values still go through its own tools.

**Blocked by:** None

**Status:** ready-for-agent

- [x] Test: phase-start tool list contains an allowed live tool and no write
- [x] Skill text
- [x] Tests green

Spec: `.scratch/coach-followups/spec.md`.

## Comments

- A task now names a tool source in `tools=` by its name: `"live"` stands for all of that
  source's runtime tools (`ask._tools`; documented in `registry.py` and `Coach.ask`).
  Phase start's `TOOLS` adds `"live"`, so it gets exactly the chat's live reads; `READ_TOOLS`
  is untouched. A registered tool with the same name as a source would still win.
- Tests in `tests/test_live_tools.py`: the phase-start request has every allowed live tool,
  no write, its own tools and not every registered tool (`propose_change` absent); a
  phase-start Hevy lookup goes through the api.
- Skill: new rule PS-LIVE-READS in `phase-start/SKILL.md` (lookups only; values still go
  through `record_setup_value` etc. and need the user's confirmation, like a prefill).
