# 07: Waist history in chat

**What to build:** A model tool `waist_history(limit)` returning dated waist values (newest first, the phase start value included), in coach-chat's tools.

**Blocked by:** None

**Status:** ready-for-agent

- [x] Tool + schema; test through the seam
- [x] Tests green

Spec: `.scratch/coach-followups/spec.md`.

## Comments

- `waist_history(limit)` lives in `features/measurements.py` (`limit` 1–100, default 12 as the web page's
  weight detail). Registered as a plain tool, so coach-chat gets it with all the others. Listed in
  `coach-skills/schemas/TOOLS.md` and named in the coach-chat skill's read tools.
- Each value carries `source`: `measured` (sent by the user) or `phase_start` (`waist_cm_start` on the
  phase's start date). The start value of every phase in `phases` (active or ended) is included, so the
  history keeps it after a phase ends (ticket 01); a value measured on a start date wins over the setup value.
- The web weight detail (`web_weight._waist`) was left unchanged (active phase only) to keep this change local.
- Tests: `coach/tests/test_measurements.py`, "waist history in chat" (4 tests through the Coach seam).
