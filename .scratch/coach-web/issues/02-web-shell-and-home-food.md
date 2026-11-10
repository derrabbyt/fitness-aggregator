# 02: Web shell, coach API and Home food

**What to build:** The tracer bullet. The coach serves a small HTTP API, `fa-api` passes `/api/coach/` through, and the web UI becomes the coach page: bottom tabs Home · Week · Training · Setup (Week, Training, Setup placeholders), light/dark tokens following the phone's theme, day navigation (arrows + date picker) with values "as of that day", a refresh control that syncs and reloads, and one stale-data line only when stale. Home's food block works end to end: kcal eaten vs the coach's daily target with kcal left, protein / carbs / fat / fiber vs targets (eaten only before a phase), and its detail "week so far". The old day view moves to `/legacy`, reachable by URL only, never linked.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The coach's HTTP server runs inside the coach process (not published on the host); `fa-api` passes `/api/coach/` through unchanged; the coach stays the only process opening its database
- [ ] Coach-core read model `home(day)` (food part, freshness) and the food detail, each with a JSON schema; tests through the Coach seam with the existing fakes cover today, a past day (as of that day), a day before any phase, and stale vs fresh
- [ ] Refresh runs the coach's sync, then returns the read model
- [ ] Angular shell with the four tabs, routes, design tokens per `docs/design/sure-reference.md` and the direction chosen in 01; Home shows the food block and its detail; errors show inline states
- [ ] The old day view is served under `/legacy` and nothing in the UI links to it
- [ ] Production build passes; phone and desktop screenshots against schema-valid fixture data are attached to this ticket's Comments
- [ ] README (Development / web) and CLAUDE.md mention the coach HTTP API and `/api/coach/`; checked once by hand against the running stack (noted in Comments); `docker compose run --rm test` green
