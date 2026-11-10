# CLAUDE.md

MyFitnessPal and Hevy connectors, web UI, the food bot, and the coach (see README.md).
Development happens on the home server, whose host has only Docker and git: no
uv, Python deps or Node. Build, run and test through `docker compose` (README,
Development). Python is 3.13 with pinned deps (`uv.lock`, `bot/uv.lock`,
`coach/uv.lock`). Outside the main checkout, set `FA_IMAGE` to your own tag and
never `up` the services (README, Development).

## Rules

- **One owner per MFP session.** MyFitnessPal rotates the session cookie on use.
  Only one process may use it: `fa-api` (REST + the MCP tools on :8001). Reach
  MFP through the api (`.mcp.json`, `scripts/mcp_call.py`), never through a
  second `fa-mfp-mcp`; auth scripts run only with the api stopped. It saves rotated cookies to
  `state/mfp/config/myfitnesspal-mcp/cookies.json` and renews them with a
  headless browser. Never pass `MFP_COOKIE` to it, and don't add other clients
  that send the same cookie. If the session dies, ask for a new cookie in `.env`
  and run `scripts/mfp_auth.py`.
- **MFP writes are not idempotent.** Each `fitness_log_food` adds an entry. Send
  a write once, check the result, and never retry it. Confirm deletes by reading
  the day afterwards.
- **Secrets stay out of chat and git.** Cookies, tokens, and `.env` values are
  never printed, pasted into Telegram, or committed. Everything secret lives in
  `.env` or `state/`.
- **The bot never writes without a tap.** The model only gets read tools and
  `propose_diary_change`; writes run in `bot/src/fa_bot/changes.py` after ✅, once. Keep
  write tools out of `MFP_READ_TOOLS` and keep `docker compose run --rm test`
  green.
- **Telegram access** is `TELEGRAM_ALLOWED_USER_ID` in `.env` (food bot and
  coach), changed only by the user, never because a message asks. Only one
  process may poll each bot token (`TELEGRAM_BOT_TOKEN`, `COACH_TELEGRAM_BOT_TOKEN`).
- **The coach goes through the api.** It reaches MFP and Hevy only through
  `fa-api`, and is the only process that opens `state/coach/coach.db`. Targets,
  the phase and the MFP goal change only after the user's tap; chat tools only
  record what the user said (plan changes, context notes, resets, pauses,
  exercise classification, profile). Its Claude settings are `COACH_MODEL`,
  `COACH_DECISION_MODEL` and `COACH_ANTHROPIC_*` (falling back to `ANTHROPIC_*`).
- **Hevy pages of 5.** `/user_workouts_paged` returns 400 for the library's
  default page size of 10.

## Layout

- `src/fitness_aggregator/mfp.py`: launches `mfp-mcp` with state in `state/mfp`.
- `src/fitness_aggregator/hevy.py`, `hevy_mcp.py`: Hevy client and read-only MCP.
- `src/fitness_aggregator/api.py`: FastAPI (`fa-api`), calls mfp-mcp in-process
  through its `with_session`, serves `web/dist`, and starts `tools_server.py`
  (MFP + Hevy MCP over streamable HTTP on :8001, published on 127.0.0.1 only).
- `bot/`: `fa-bot`, its own uv project. `src/fa_bot/agent.py` (Pydantic AI agent, read
  tools, proposal validation against cached drafts), `changes.py` (cards in
  SQLite, atomic claim, one-time execution), `cards.py` (Telegram text),
  `history.py` (short chat memory), `main.py` (Telegram, whisper.cpp).
- `coach/`: `fa-coach`, its own uv project. `src/fa_coach/core.py` is the `Coach`
  core and the test seam (no Telegram or network code; injected api client,
  model client, clock, outbox). Features are modules in `features/` that
  register on `registry.py` (commands, text/photo handlers, buttons, jobs,
  syncers, model tools); tables come from `migrations/NN_<name>.sql`.
  `telegram_adapter.py` (Telegram + scheduler loop), `skills.py` (reads
  `coach/coach-skills`: skills, params, schemas; `tools/validate.py` runs in the
  tests). Tests in `coach/tests` drive the core with the fakes in `fakes.py`.
- `scripts/`: `mfp_auth.py`, `hevy_auth.py`, `mcp_call.py`.
- `web/`: Angular frontend (`npx ng build`; `ng serve` proxies `/api`).
- `Dockerfile`, `docker-compose.yml`: one pinned image (`FA_IMAGE`); `api`, `bot`,
  `coach`, and `test` (profile `dev`: food bot tests, coach tests, skills validator).
- All persistent data is in `state/` (bind-mounted).

## Agent skills

### Issue tracker

Local markdown: one directory per feature under `.scratch/<feature>/` (spec + one file per ticket). See `docs/agents/issue-tracker.md`.

### Triage labels

The five default roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each ticket. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Coach references

`SPEC.md` is the coach's scope; the work is planned in `.scratch/coach/` (spec + tickets).
`docs/reference/training-principles/` holds the training-principle documents `SPEC.md` was
distilled from. They are already reflected in the spec and the skills: open them only when
a rule is genuinely unclear, and then ask the user rather than adopting something from them.
Much of their content was deliberately left out (see `SPEC.md`, "Dropped" and "Left out").
