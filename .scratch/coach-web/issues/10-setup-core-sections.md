# 10: Setup: sections, phase and targets, messaging, activity values

**What to build:** The Setup tab lists its sections with one-line summaries (Phase & targets, Activity values, Messaging, Training plan, Exercises, Context notes, Profile, Measurements; later sections may show "coming soon" until 11–12 land). Phase & targets shows the active phase, phase week, base maintenance, surplus, step goal and current daily targets, and lets the user change the step goal. Messaging (check-in day and time, evening reminder time, daily message limit, step-floor window) saves directly. Activity values (run discount, wrestling kcal, lifting kcal) can be edited, and a change becomes a calibration proposal the user approves in Telegram. Starting a phase stays in Telegram.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Coach-core read model `setup()` and section views with schemas; edit commands share validation with chat (`record_setup_value`, calibration proposals); tests cover each edit, each rejection with its reason, and a calibration edit creating a proposal (and the Telegram card)
- [ ] No web path changes targets, the phase or the MFP goal directly
- [ ] UI list and edit pages with inline confirmation / error; build + screenshots in Comments; tests green
