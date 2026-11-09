# fitness-aggregator

My fitness data from MyFitnessPal and Hevy: MCP connectors, a small web UI, and
a Telegram bot for logging food (text, voice, photos) and quick questions. Runs
in Docker on my home server; development happens there too, with nothing but
Docker and git on the host.

| Connector | What | Source |
|---|---|---|
| `mfp` | MyFitnessPal: diary, food search and logging, exercise, weight, water, trends, export | [Mason-Levyy/myfitnesspal-mcp](https://github.com/Mason-Levyy/myfitnesspal-mcp) (pinned) |
| `hevy` | Hevy workouts, read-only | `src/fitness_aggregator/hevy_mcp.py` on [hevy-unofficial](https://github.com/Sahil624/hevy-unofficial) (pinned) |

Both use unofficial APIs, which can break or get an account flagged.

## Services

| Service | What |
|---|---|
| `api` (`fa-api`) | FastAPI + web UI on `:8000` (`/api/day?date=YYYY-MM-DD`, `/api/today`), and the MFP/Hevy MCP tools on `:8001` (`/mfp/mcp`, `/hevy/mcp`). The only user of the MFP session. |
| `bot` (`fa-bot`) | Telegram bot. Pydantic AI agent on `BOT_MODEL` with the api's MCP tools; voice notes via whisper.cpp. |

`:8000` is published on `FA_BIND`. `:8001` is published on the host's
`127.0.0.1` only, for Claude Code: anything that reaches it can write to the
diary.

## Development

Everything runs in the one image; the host needs only Docker and git.

```bash
docker compose up -d --build        # rebuild + restart after any code change
docker compose logs -f bot          # or api
docker compose run --rm test        # bot tests on the working tree, no rebuild needed
```

- **Bot code** (`bot/src/fa_bot`): edit, `docker compose run --rm test`, then
  `docker compose up -d --build bot`. Only the last layers rebuild.
- **Api code** (`src/fitness_aggregator`): `docker compose up -d --build api`
  (this restarts the bot too, since it depends on the api).
- **Web UI** (`web/`): `docker compose up -d --build api` rebuilds it. No Node
  on the host; for a live dev server use
  `docker run --rm -it -v ./web:/web -w /web -p 4200:4200 node:22-bookworm-slim sh -c "npm ci && npx ng serve --host 0.0.0.0"`
  (its `/api` proxy expects the api on the same host's `:8000`).
- **Dependencies:** `uv.lock` and `bot/uv.lock` are pinned. To change one,
  e.g. `docker run --rm -v ./bot:/w -w /w ghcr.io/astral-sh/uv:0.11.29 uv lock --upgrade-package <pkg>`,
  then rebuild.
- **Calling the tools from a shell** (goes through the running api):

  ```bash
  docker compose exec api python scripts/mcp_call.py mfp --list
  docker compose exec api python scripts/mcp_call.py hevy '[["hevy_list_workouts", {"limit": 3}]]'
  ```

- **Claude Code** on the host gets the same tools from `.mcp.json`
  (`http://127.0.0.1:8001`), so it needs the api running. That includes MFP
  write tools, unlike the bot.

## Connecting accounts

Both are one-off containers, run with the api stopped so only one process
touches the sessions:

```bash
docker compose stop api bot
# MyFitnessPal: put MFP_COOKIE (the __Secure-next-auth.session-token value from
# a private-window login) in .env, then:
docker compose run --rm --no-deps -v ./.env:/app/.env:ro api python scripts/mfp_auth.py
# Hevy: paste the auth2.0-token cookie from hevy.com (no browser login on the server):
docker compose run --rm --no-deps -T api python scripts/hevy_auth.py --cookie < cookie.txt
docker compose up -d
```

`scripts/mfp_auth.py --check` tests the saved MFP session. Remove `MFP_COOKIE`
from `.env` (and `cookie.txt`) afterwards.

## Telegram bot

- **Only you:** messages from anyone but `TELEGRAM_ALLOWED_USER_ID` are ignored.
  Only one process may poll a bot token.
- **Nothing is written without a tap.** The model has read-only MFP tools plus
  `propose_diary_change`, which shows a card (date, foods, kcal, P/C/F) with
  ✅/❌. The bot's own code runs the writes after ✅, once, never retried, and
  then shows what is actually in the diary. Cards expire after 30 minutes; a
  new card replaces an older pending one; dates more than 7 days back get a ⚠️.
- **Finding foods:** your diary history first (`find_past_foods`), then the MFP
  search. If nothing fits (restaurant or homemade food), the card offers an
  estimated **Quick Add** (kcal + macros, marked "≈ estimate"); "add 300 kcal"
  is a plain Quick Add. Quick Add uses MFP's v2 API (`fitness_quick_add` on the
  api's tools endpoint; only the bot's code calls it, after ✅).
- **Memory:** the last 10 exchanges from the last 6 hours (`state/bot/bot.db`).
- **Costs:** at most 15 model calls per message; usage per message in
  `state/bot/usage.jsonl`.
- **Model:** `BOT_MODEL` is any Pydantic AI model string
  (`anthropic:claude-sonnet-5-5`, `openai:…`); set that provider's API key, and
  `*_BASE_URL` for a proxy or an OpenAI-compatible server.

## Layout

```
src/fitness_aggregator/    api: REST + UI, MCP tools over HTTP (tools_server.py),
                           MFP launcher, Hevy client and MCP server
bot/                       fa-bot, its own uv project (pydantic-ai can't share
  src/fa_bot/              mfp-mcp's pinned deps): agent, cards, changes, memory
  tests/                   card/confirmation logic
web/                       Angular UI
scripts/                   auth and shell helpers
state/                     sessions, tokens, bot data, logs (gitignored, 0700)
```

Moving machines: the repo, `.env`, and `state/`, with the old copy stopped
first (one MFP session owner, one bot poller).
