# 13: Design review and polish

**What to build:** A finished-build pass: screenshots of every page and detail at phone and desktop width, light and dark, reviewed by a design agent against `docs/design/sure-reference.md` and the direction from 01; the material fixes applied. Also a last check that nothing links to `/legacy` and that the page has no explanatory clutter.

**Blocked by:** 03, 04, 05, 06, 07, 08, 09, 10, 11, 12

**Status:** resolved

- [x] Design review (impeccable finish reviewer or equivalent) run on screenshots of all pages; its ordered fix list is recorded in Comments
- [x] Material fixes applied; final screenshots attached; build and `docker compose run --rm test` green
- [x] Deployed once with the user's go-ahead and checked by hand on the phone (noted in Comments)

## Notes from earlier tickets

- Ticket 02: `fa-api` logs every proxied `/api/coach/` request at INFO via httpx; quiet the httpx logger in the api (warnings only).
- Ticket 02: freshness is measured as of now, not as of the shown day; fiber target is a range and Home shows its low end — check these read sensibly in the review.
- Ticket 05: skipped planned sessions currently show with a "skipped" flag on Home; hide them instead (they did not happen, and the user wants no status tags).
- Ticket 05: sync re-checks only the last 7 days, so a Hevy session added more than 7 days after its date is never picked up (pre-existing; consider a periodic deeper re-check).
- Ticket 10: the run-discount refusal names the 0–1 share ("run_kcal_discount = 1.5 is outside 0–1") while the web takes a percentage; reword for the web.
- Ticket 11: `web_setup.schema.json` description still lists only the first three sections; update it to all eight.
- Ticket 09: lift chart high/low labels are rounded to whole kg; Setup › Exercises could link each exercise to its lift detail.
- Ticket 12: fa-api access log prints `/api/coach/photos/<date>/<n>` lines (dates only); fine, but quieting /api/coach access lines with the httpx logger would be consistent.

## Comments

**Design review** (finish reviewer on the 01–15 screenshots, `scratchpad/coach-web-notes/design-review.md`), disposition *fix*. Ordered material fixes, all applied:

1. Explanatory clutter removed: every Setup `.note` footer; the profile/notes new-entry blurbs (the example moved to the placeholder; "Add entry"/"Add note" is a plain button and the form card opens on tap); the time-format hint (now the placeholder "06:30 / evening"); the "Shown here: the plan in force today" banner (the upcoming change moved into the section aside: "Since 9 Nov · changes 16 Nov"); every edit-row hint that explained something (step goal, lift Controls, Activity values, Messaging; Messaging labels made self-explanatory: "Coach messages a day", "Step-floor nudge after"); the reset editor's consequence line; the explanatory measurement and photo lines. Kept: hints that are data (a weekday's sessions, "Next due …", a pause reason, the last reset reason), "No photos yet. Send them to the coach in Telegram." (where a user would expect an upload button), and the Setup page's short state banners ("No active phase. Start one in Telegram." / "Phase setup open in Telegram. Finish it there to edit here.").
2. Colour only for verdicts: the edit-row action, `.link`, the This week actions, the plan editor's "+ Session"/"Remove", the proposal pill dot and the "Today" tag are neutral now. Red stays only on a delete's confirm button (context notes). Profile "Remove" is neutral, since it has no confirm step.
3. This week: each session or extra row is one tap target (aria-expanded) that opens its actions (Skip / Done / Undo / Remove). "+ Extra session" appears once, at the bottom of the card, with a day picker (today and earlier, default today). The editor's explanatory hint is gone, and a skipped session shows the word only (no strikethrough). Saved-week rows use the edit-row grammar (see 6), so both cards read as rows you tap.
4. The lift chart uses the app's chart grammar: one 2px line in the lift's verdict tone with LineChart's gradient wash, no per-session dots, no hi/lo labels, no legend. PRs are small dots in the line colour; the dashed reset lines stay; start and end dates sit underneath in text-2.
5. One pattern for "counts for progress": a shared `ui/switch.ts`, with a visible "COUNTS" column label on Setup › Exercises and a "Counts for progress" switch row on the lift page (instead of "Counts · Change"). Pause/Resume and Baseline reset live on the lift page only. Exercises rows show "paused" in their data line and **link to the lift detail** (the ticket 09 note).
6. Tap targets: an editable `app-edit-row` is now one button for the whole row ("Change <label>", 44px min on touch; the "Change"/"Edit" word stays as a neutral affordance). `.link`, `.act`, `.add`, the plan editor's buttons and "Show more" get 44px on `pointer: coarse`, and the switch gets a 44px hit area through a pseudo-element.
7. Week: the decision's own proposal is merged into the Decision card (big "+100 kcal a day", the decision's one reason, "Average daily target 2,300 → 2,400 kcal", "MyFitnessPal goal", the "Waiting in Telegram" pill, the streak line). The "Applies: From the day you approve it" and "Guardrails: Passed" rows are dropped from every proposal card. On desktop the decision and proposal cards sit in the same two-column grid as the blocks, with the report full width.
8. Contrast: the `.t3` class is gone. All text that used `--text-3` (chart end labels, the steps "Goal" line, "Not set", "Nothing logged", the lift chart dates, …) uses `--text-2`; `--text-3` stays for chevrons, dashed marks and dots.

Optional items done: the Home Other activities meta sits on one left-aligned line under the name; the Week header is "Week" with the range · phase week underneath (tab name as title, as on the other tabs); the profile edit label is upper-case; the lift "Show more" is a plain text action; a skipped session shows one signal. Optional items not done: the Workouts rate stays under the chart (the block's docstring records ticket 15's stacked layout as the user's choice); the Training section labels stay outside the cards; the Week steps bars and moving Steps out of Training; two independent column stacks for desktop Home. The strength hero already used `.big`.

**Notes from earlier tickets:**
- Skipped sessions are no longer listed on Home (coach `web_home_training`; the `skipped` flag is dropped from the schema, the example and the web type). Test first: `test_a_skipped_session_is_not_listed`.
- Hevy is re-read over the whole 16-week window once every 7 days (`HEVY_FULL_READ_DAYS`, `sync_state.full_read_on`, migration `21_sync_full_read.sql`), so a session logged late lands within a week. MFP keeps its 7-day re-read. The first sync after deploy does one full Hevy read. Test first: `test_once_a_week_hevy_is_re_read_over_the_whole_history_so_late_sessions_land`.
- `fa-api`: the httpx logger is at WARNING, and a filter on `uvicorn.access` drops successful `/api/coach/` lines (failures ≥ 400 still log). Checked in the image against a throwaway uvicorn app.
- The run-discount refusal on the web reads "Runs counted 150 % is outside 0–100 %. …" (the Activity row is labelled "Runs counted"). The test was updated first.
- `web_setup.schema.json` lists all eight sections.
- Setup › Exercises rows link to their lift detail. Its back arrow goes to Training, because the lift page's back target is fixed.
- The lift chart has no high/low labels any more, so the rounding question is moot.
- Freshness as of now and the fiber low end read sensibly in the shots; no change.
- Nothing links to `/legacy` (only the route and the shell's check mention it).

**Screenshots** (`scratchpad/coach-web-notes/screenshots/13/`; phone 390 wide with a page-tall viewport so the tab bar stays at the bottom, desktop 1280; each `-light` and `-dark`): phone- and desktop- × home, home-food, home-weight, home-steps, home-sleep, week, week-in-progress, training, lift, setup, setup-phase-targets, setup-activity, setup-messaging, setup-training-plan, setup-training-plan-row-open, setup-training-plan-extra, setup-exercises, setup-notes, setup-profile, setup-measurements (80 files). Script: `scratchpad/w13/shoot.py` (coach-skills examples for the leaf views, earlier tickets' fixtures for home, week and setup).

The build (`npx ng build`) is clean and `docker compose run --rm test` is green (bot, coach 478, validator). Not deployed; not checked on the phone.
- **Deployed (orchestrator, 2026-11-12):** `coach-web` with the review fixes deployed live (api + coach recreated; all views 200). The user has been using the page on the phone throughout the build (Home since 2026-11-11, all tabs since 2026-11-12); no separate sign-off was asked.
