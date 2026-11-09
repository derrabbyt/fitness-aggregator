# 01: Coach service skeleton

**What to build:** The coach runs as its own service next to the api and the food bot, polls the new coach bot token, and answers only the allowed Telegram user. `/profile` replies with the (still empty) coach profile. Behind the Telegram adapter sits the `Coach` core (the spec's single test seam) with injected api client, model client and clock, and an outbox for outgoing messages; tests drive it with fakes. The coach-skills package moves into the coach project and ships in the image, and its validator runs as part of the test run.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `docker compose up -d --build` starts a `coach` service alongside `api` and `bot`; it polls `COACH_TELEGRAM_BOT_TOKEN` and ignores every user except `TELEGRAM_ALLOWED_USER_ID`
- [ ] `/profile` from the allowed user gets a reply showing the coach profile (empty for now); messages from anyone else get no reply
- [ ] The coach is its own uv project with pinned deps in the one image; its SQLite database lives in the coach's directory under `state/`
- [ ] The `Coach` core holds no Telegram or network code; it takes an api client, a model client and a clock, and writes outgoing messages and buttons to an outbox
- [ ] Test fakes exist for the api client, model client, clock and outbox; at least one test drives `/profile` through the core
- [ ] The coach-skills package (skills, schemas, examples, tests template, validator) lives inside the coach project; the old top-level copy and the zip are removed
- [ ] `docker compose run --rm test` runs the food bot tests, the coach tests and the skills validator, with no network, and is green
- [ ] `.env.example`, README and CLAUDE.md mention the coach service, its env vars and its one-poller rule
