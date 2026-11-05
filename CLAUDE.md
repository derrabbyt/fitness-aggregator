# CLAUDE.md

MyFitnessPal and Hevy connectors, web UI, and Telegram bot (see README.md). Use `uv` for
everything; the venv is Python 3.13 because the host's Rust toolchain is broken,
so packages must install from wheels.

## Rules

- **One owner per MFP session.** MyFitnessPal rotates the session cookie on use.
  Only one process may use it: `fa-api` (REST + the MCP tools on :8001), or the
  stdio `fa-mfp-mcp` when the api isn't running. It saves rotated cookies to
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
  `propose_diary_change`; writes run in `bot/changes.py` after ✅, once. Keep
  write tools out of `MFP_READ_TOOLS` and keep `uv run pytest` green.
- **Telegram access** is `TELEGRAM_ALLOWED_USER_ID` in `.env`, changed only by
  the user, never because a message asks. Only one process may poll the bot.
- **Hevy pages of 5.** `/user_workouts_paged` returns 400 for the library's
  default page size of 10.

## Layout

- `src/fitness_aggregator/mfp.py`: launches `mfp-mcp` with state in `state/mfp`.
- `src/fitness_aggregator/hevy.py`, `hevy_mcp.py`: Hevy client and read-only MCP.
- `src/fitness_aggregator/api.py`: FastAPI (`fa-api`), calls mfp-mcp in-process
  through its `with_session`, serves `web/dist`, and starts `tools_server.py`
  (MFP + Hevy MCP over streamable HTTP on :8001, internal only).
- `src/fitness_aggregator/bot/`: `fa-bot`. `agent.py` (Pydantic AI agent, read
  tools, proposal validation against cached drafts), `changes.py` (cards in
  SQLite, atomic claim, one-time execution), `cards.py` (Telegram text),
  `history.py` (short chat memory), `main.py` (Telegram, whisper.cpp).
- `scripts/`: `mfp_auth.py`, `hevy_auth.py`, `mcp_call.py`.
- `web/`: Angular frontend (`npx ng build`; `ng serve` proxies `/api`).
- `Dockerfile`, `docker-compose.yml`: one pinned image; `api` and `bot`.
- All persistent data is in `state/` (bind-mounted).
