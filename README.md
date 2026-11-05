# fitness-aggregator

My fitness data from MyFitnessPal and Hevy: MCP connectors, a small web UI, and
a Telegram bot for logging food (text, voice, photos) and quick questions. Runs
in Docker on my home server, reachable over Tailscale.

| Connector | What | Source |
|---|---|---|
| `mfp` | MyFitnessPal: diary, food search and logging, exercise, weight, water, trends, export | [Mason-Levyy/myfitnesspal-mcp](https://github.com/Mason-Levyy/myfitnesspal-mcp) (pinned) |
| `hevy` | Hevy workouts, read-only | `src/fitness_aggregator/hevy_mcp.py` on [hevy-unofficial](https://github.com/Sahil624/hevy-unofficial) (pinned) |

Both use unofficial APIs, which can break or get an account flagged.

## Setup

```bash
uv sync                                   # Python 3.13, pinned deps
cp .env.example .env && chmod 600 .env    # fill in MFP_USERNAME and MFP_COOKIE
uv run playwright install chromium        # once, for MFP auto-refresh and Hevy login
uv run scripts/mfp_auth.py                # connect MyFitnessPal (auto-refresh on)
uv run scripts/hevy_auth.py               # connect Hevy (browser login, or --cookie)
```

## Running

| Process | What |
|---|---|
| `fa-api` | FastAPI + web UI on `:8000` (`/api/day?date=YYYY-MM-DD`, `/api/today`), and the MFP/Hevy MCP tools on `:8001` (`/mfp/mcp`, `/hevy/mcp`). The only owner of the MFP session. |
| `fa-bot` | Telegram bot. Pydantic AI agent on `BOT_MODEL` with the api's MCP tools; voice notes via whisper.cpp. |

```bash
docker compose up -d --build        # both services
docker compose logs -f bot
uv run pytest                       # card/confirmation logic, no network
```

Locally without Docker: `(cd web && npm ci && npx ng build)`, then `uv run fa-api`
and `uv run fa-bot` (needs `whisper-cli` and `ffmpeg` on the PATH for voice).
For frontend work, `cd web && npx ng serve` (http://localhost:4200, proxies
`/api` to :8000).

Moving machines: copy the repo, `.env`, and `state/`, then
`docker compose up -d --build`. On the server, set `FA_BIND` to its Tailscale IP.
Port 8001 is never published: anything that reaches it can write to the diary.

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
  (`anthropic:claude-sonnet-5-5`, `openai:…`); set that provider's API key.

## Claude Code on the host

`.mcp.json` registers the stdio `mfp` and `hevy` servers. The `mfp` one uses the
same session files as `fa-api`, so don't use it while the api runs. From a
shell:

```bash
uv run scripts/mcp_call.py mfp --list
uv run scripts/mcp_call.py hevy '[["hevy_list_workouts", {"limit": 3}]]'
```

## Layout

```
src/fitness_aggregator/
  api.py, tools_server.py  REST + UI, MCP tools over HTTP (one process)
  bot/                     Telegram bot: agent, cards/confirmation, memory
  mfp.py, hevy*.py         connector launchers, Hevy client and MCP server
web/                       Angular UI
scripts/                   auth and shell helpers
tests/                     confirmation logic
state/                     sessions, tokens, bot data, logs (gitignored, 0700)
```
