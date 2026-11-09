# fitness-aggregator

My fitness data from MyFitnessPal and Hevy: MCP connectors, a small web UI, a
Telegram bot for logging food (text, voice, photos) and quick questions, and a
coach (a second Telegram bot) that watches the data and proposes plan changes
(`SPEC.md`, `.scratch/coach/`). Runs in Docker on my home server; development
happens there too, with nothing but Docker and git on the host.

| Connector | What | Source |
|---|---|---|
| `mfp` | MyFitnessPal: diary, food search and logging, exercise, weight, water, trends, export | [Mason-Levyy/myfitnesspal-mcp](https://github.com/Mason-Levyy/myfitnesspal-mcp) (pinned) |
| `hevy` | Hevy workouts, read-only | `src/fitness_aggregator/hevy_mcp.py` on [hevy-unofficial](https://github.com/Sahil624/hevy-unofficial) (pinned) |

Both use unofficial APIs, which can break or get an account flagged.

## Services

| Service | What |
|---|---|
| `api` (`fa-api`) | FastAPI + web UI on `:8000` (`/api/day?date=YYYY-MM-DD`, `/api/today`), and the MFP/Hevy MCP tools on `:8001` (`/mfp/mcp`, `/hevy/mcp`). The only user of the MFP session. |
| `bot` (`fa-bot`) | Food bot (Telegram). Pydantic AI agent on `BOT_MODEL` with the api's MCP tools; voice notes via whisper.cpp. |
| `coach` (`fa-coach`) | The coach (its own Telegram bot). Syncs MFP and Hevy data through the api into `state/coach/coach.db`, calls Claude through the Anthropic SDK. |

`:8000` is published on `FA_BIND`. `:8001` is published on the host's
`127.0.0.1` only, for Claude Code: anything that reaches it can write to the
diary.

## Development

Everything runs in the one image; the host needs only Docker and git.

```bash
docker compose up -d --build        # rebuild + restart after any code change
docker compose logs -f coach        # or api, bot
docker compose run --rm test        # tests on the working tree, no rebuild needed
```

- **Tests:** `docker compose run --rm test` runs the food bot's tests, the
  coach's tests and the coach-skills validator against the mounted sources,
  with no network. Rebuild first only when dependencies change.
- **Bot code** (`bot/src/fa_bot`): edit, `docker compose run --rm test`, then
  `docker compose up -d --build bot`. Only the last layers rebuild.
- **Coach code** (`coach/src/fa_coach`, skills in `coach/coach-skills`): edit,
  `docker compose run --rm test`, then `docker compose up -d --build coach`.
- **Api code** (`src/fitness_aggregator`): `docker compose up -d --build api`
  (this restarts the bot too, since it depends on the api).
- **Web UI** (`web/`): `docker compose up -d --build api` rebuilds it. No Node
  on the host; for a live dev server use
  `docker run --rm -it -v ./web:/web -w /web -p 4200:4200 node:22-bookworm-slim sh -c "npm ci && npx ng serve --host 0.0.0.0"`
  (its `/api` proxy expects the api on the same host's `:8000`).
- **Dependencies:** `uv.lock`, `bot/uv.lock` and `coach/uv.lock` are pinned.
  To change one, e.g.
  `docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v ./coach:/w -w /w ghcr.io/astral-sh/uv:0.11.29-debian-slim uv lock --upgrade-package <pkg>`
  (or `uv add <pkg>`), then rebuild.
- **Second checkout or worktree:** every service uses the image named by
  `FA_IMAGE` (default `fitness-aggregator:latest`). Give other checkouts their
  own tag so their builds don't replace the image the running services use,
  and pass dummies for the required variables if that checkout has no `.env`:

  ```bash
  export FA_IMAGE=fitness-aggregator:mybranch MFP_USERNAME=x TELEGRAM_BOT_TOKEN=x \
    TELEGRAM_ALLOWED_USER_ID=1 COACH_TELEGRAM_BOT_TOKEN=x
  docker compose build api && docker compose run --rm test
  ```

  Never `up` the services from a second checkout: each bot token and the MFP
  session may have only one user.
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
docker compose stop api bot coach
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

## Coach

- **Its own bot:** `COACH_TELEGRAM_BOT_TOKEN` is a second bot, not the food
  bot's. Only one process may poll it. It answers only
  `TELEGRAM_ALLOWED_USER_ID`, like the food bot.
- **Data:** it syncs from the api (never from MFP or Hevy directly) into
  `state/coach/coach.db`, which only the coach opens.
- **Claude:** `COACH_MODEL` for chat and daily messages, `COACH_DECISION_MODEL`
  for the weekly decision; `COACH_ANTHROPIC_API_KEY` / `COACH_ANTHROPIC_BASE_URL`
  fall back to `ANTHROPIC_*`.
- **Commands:** `/profile` shows the coach profile.
- **Chat:** free text goes to the model with the coach-chat and context-log
  skills. Context (sick, travel, camp week, creatine) is stored as a dated,
  tagged context note in your words; preferences go into the profile. Memory:
  the last 3 exchanges from the last 12 hours.
- **Code:** `coach/src/fa_coach/core.py` is the `Coach` core: no Telegram or
  network code, driven by tests with fakes. Model tasks run through
  `coach.ask(...)` (`ask.py`: prompt layout, tool loop, schema-checked JSON);
  `model.py` maps them onto the Anthropic SDK. Features are modules in
  `coach/src/fa_coach/features/` that register commands, buttons, jobs,
  syncers, state-snapshot entries and model tools (`registry.py`); tables come from
  `coach/src/fa_coach/migrations/NN_<name>.sql`. The skills package
  (`coach/coach-skills`: skills, params, schemas, validator) ships in the image.

## Layout

```
src/fitness_aggregator/    api: REST + UI, MCP tools over HTTP (tools_server.py),
                           MFP launcher, Hevy client and MCP server
bot/                       fa-bot, its own uv project (pydantic-ai can't share
  src/fa_bot/              mfp-mcp's pinned deps): agent, cards, changes, memory
  tests/                   card/confirmation logic
coach/                     fa-coach, its own uv project: Coach core, features,
  src/fa_coach/            Telegram adapter, scheduler
  coach-skills/            skills, params, schemas, validator
  tests/                   through the Coach core, with fakes
web/                       Angular UI
scripts/                   auth and shell helpers
state/                     sessions, tokens, bot data, logs (gitignored, 0700)
```

Moving machines: the repo, `.env`, and `state/`, with the old copy stopped
first (one MFP session owner, one poller per bot).
