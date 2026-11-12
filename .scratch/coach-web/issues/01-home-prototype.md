# 01: Home prototype (throwaway)

**What to build:** A throwaway prototype of Home at phone width (and a quick desktop check) with realistic fixture data, in the Sure-style direction (`docs/design/sure-reference.md`, spec "Frontend"), for the user to react to before Home is built. It settles the visual direction: the food block in the common food-tracking style (kcal eaten / target with "left", macros + fiber bars), the weight, steps, training and sleep blocks, the banner and stale line, the bottom tabs, light and dark. Not wired to real data and not shipped.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] Use the prototype skill; the prototype lives outside the shipped app (or behind a throwaway route) and is easy to delete
- [x] Phone-width screenshots, light and dark, plus one desktop-width screenshot, saved where the user can open them
- [x] Fixture data covers: a normal day, a day before any phase (no target), no sleep data, a not-tracked steps day, an open proposal banner
- [x] The user's feedback and the chosen direction (incl. food block style) are recorded in this ticket's Comments; the prototype is then removed or left clearly marked as throwaway

## Comments
- **Prototype:** static HTML on branch `web/01-home-prototype` (`prototypes/home/`), not merged (throwaway). Screenshots: `/tmp/claude-1000/-home-debian-projects-fitness-aggregator/5741d455-db4e-4fd2-8a29-efc585325ab1/scratchpad/coach-web-notes/screenshots/01/`.
- **User's direction (2026-11-10):** keep the look (Sure-style cards, colour only for on/off target, dark mode, bottom tabs; desktop centred, two columns, tabs as a segmented control in the header); bundle Geist. Changes:
  - **Food: the bar variant** — "kcal left" big, eaten / target on the right, one bar, then protein / carbs / fat / fiber as four compact columns with thin bars.
  - **Weight:** today's weigh-in big, the weekly rate (coloured vs band) and the 14-day line; **no "trend" value and no band text** on Home (both stay in the weight detail).
  - **Training split in two blocks:** **Gym** (lifting sessions, one line each with time and duration, and the lift trend line under them) and **Other activities** (runs with distance, duration and **pace**, wrestling, extra sessions). **No "planned" tag.**
- **Boxes (orchestrator):** the prototype, its screenshots and the fixture states were delivered on the unmerged throwaway branch `web/01-home-prototype`; ticked here.
