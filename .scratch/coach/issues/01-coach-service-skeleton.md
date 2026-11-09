# 01: Coach service skeleton

**What to build:** The coach runs as its own service next to the api and the food bot, polls the new coach bot token, and answers only the allowed Telegram user. `/profile` replies with the (still empty) coach profile. Behind the Telegram adapter sits the `Coach` core (the spec's single test seam) with injected api client, model client and clock, and an outbox for outgoing messages; tests drive it with fakes. The coach-skills package moves into the coach project and ships in the image, and its validator runs as part of the test run.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `docker compose up -d --build` starts a `coach` service alongside `api` and `bot`; it polls `COACH_TELEGRAM_BOT_TOKEN` and ignores every user except `TELEGRAM_ALLOWED_USER_ID`
- [x] `/profile` from the allowed user gets a reply showing the coach profile (empty for now); messages from anyone else get no reply
- [x] The coach is its own uv project with pinned deps in the one image; its SQLite database lives in the coach's directory under `state/`
- [x] The `Coach` core holds no Telegram or network code; it takes an api client, a model client and a clock, and writes outgoing messages and buttons to an outbox
- [x] Test fakes exist for the api client, model client, clock and outbox; at least one test drives `/profile` through the core
- [x] The coach-skills package (skills, schemas, examples, tests template, validator) lives inside the coach project; the old top-level copy and the zip are removed
- [x] `docker compose run --rm test` runs the food bot tests, the coach tests and the skills validator, with no network, and is green
- [x] `.env.example`, README and CLAUDE.md mention the coach service, its env vars and its one-poller rule

## Comments

- Not done here: `docker compose up -d --build` with a real `COACH_TELEGRAM_BOT_TOKEN` (the rules forbid starting services from a worktree). Checked instead: the image builds (`FA_IMAGE=fitness-aggregator:coach-01`), `docker compose config` is valid with the new `coach` service, and the adapter's delivery (send, chunking, buttons, edit by ref, error reply) was smoke-run offline against a fake bot. The access check (`filters.User` plus an explicit user-id check in each handler, as in the food bot) is in the Telegram adapter, which the spec leaves untested in v1.
- Build fix: commit e9bd649 renamed README.md to README.legacy.md while the Dockerfile still copied README.md; it's moved back to README.md and updated.
- `FA_IMAGE` (default `fitness-aggregator:latest`) names the image for every service, so worktrees build and test under their own tag. `.claude` is in `.dockerignore`. The `test` service runs with `network_mode: none`.
- The package lives at `coach/coach-skills` (keeps its name; `coach/skills` would give `coach/skills/skills/`). The validator runs inside the coach's pytest run (`tests/test_skills_package.py`), so a failure shows as a test failure. The zip was untracked in the main checkout; the orchestrator removes it.
- The core is async (Anthropic, MCP and Telegram clients are async); the adapter runs one core call at a time.
- Extension points for later tickets (so they add files rather than edit shared lines): feature modules in `fa_coach/features/` are auto-imported and register on `fa_coach/registry.py` (commands, ordered text/photo handlers, buttons, jobs, syncers, model tools as Anthropic tool definitions); tables come from `fa_coach/migrations/NN_<name>.sql` (NN = ticket number, applied once each by file name); `coach.db.once(key, now)` gives once-per-day/week/session rules; `Send(ref=...)` / `Edit(ref)` let a button handler replace a card's text and remove its buttons; `coach.skills` reads skills, merged params (phase wins) and validates against the schemas.
- Deps are pre-added for the planned work so later tickets don't fight over `coach/uv.lock`: `anthropic`, `httpx`, `mcp` (for `fitness_set_goal`), `python-telegram-bot`, `jsonschema`, `pyyaml`.
- `ports.ModelRequest` / `ModelReply` / `ToolCall` are a first sketch of the model client interface; ticket 03 may reshape them together with `FakeModel`. `model.py` is a placeholder that fails if called.
- Until the chat exists (ticket 03), free text and unknown commands get a one-line reply listing the commands.
