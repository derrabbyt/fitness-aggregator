# 05: Phase start: reverse

**What to build:** "start reverse" in the coach chat starts setting up the reverse-into-bulk phase. The coach prefills what it can read from the synced history (last diet intake, starting trend weight, maintenance estimate, main lifts from Hevy) and asks only for what's missing, a few items per message: tracked lifts, run discount, wrestling kcal, lifting kcal per session, fat start, week-1 increase, optional time goal, photos on/off, waist at start, and logistics (check-in day and time, evening reminder time, message limit, step-floor window). Code computes a week-1 preview; nothing changes until the user taps confirm.

**Blocked by:** 02 (Sync history from MFP and Hevy), 04 (Training plan in chat)

**Status:** ready-for-agent

- [ ] The phase-start skill is loaded with the target phase skill; draft phases with undecided values are refused, listing what must be decided
- [ ] Prefilled values come from code-computed history and are shown for confirmation, never guessed
- [ ] `record_setup_value` stores each value as soon as it's given and validates it against the params and phase-setup schemas
- [ ] A new setup value, lifting kcal per session, exists in core params, the phase-setup schema and the phase-start skill
- [ ] `start_phase` stores a pending phase and returns a code-computed preview: average daily target, the MFP goal it will set, daily targets on rest / lifting / run / wrestling days, and macros (protein and fat in g/kg of the current 7-day trend weight, carbs as remainder)
- [ ] The preview message explains the glycogen window and the expected early jump, and has confirm and edit buttons
- [ ] Confirm makes the phase active, stores targets and marks the phase's first change applied; edit returns to collecting values; before confirm nothing is active
- [ ] A second tap on confirm does nothing (atomic claim)
- [ ] Tests cover a full start with a scripted model, refusal of a draft phase, edit-then-confirm, and that nothing is active before confirm
