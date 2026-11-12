# 08: Live reads in phase start

**What to build:** The phase-start task gets the `live` tool source (the read-only `READ_TOOLS` allowlist, unchanged). The phase-start skill says live reads are for looking things up; setup values still go through its own tools.

**Blocked by:** None

**Status:** ready-for-agent

- [ ] Test: phase-start tool list contains an allowed live tool and no write
- [ ] Skill text
- [ ] Tests green

Spec: `.scratch/coach-followups/spec.md`.
