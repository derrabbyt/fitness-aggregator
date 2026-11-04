# fitness-aggregator

Agent connectors for my fitness data. Two MCP servers, a Telegram channel, and
(later) skills and a small FastAPI + web UI served on my home server over
Tailscale.

| Server | What | Source |
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

Claude Code picks up both servers from `.mcp.json`. To call them from a shell:

```bash
uv run scripts/mcp_call.py mfp --list
uv run scripts/mcp_call.py mfp '[["fitness_get_day", {}]]'
uv run scripts/mcp_call.py hevy '[["hevy_list_workouts", {"limit": 3}]]'
```

## Telegram

`.claude/settings.json` enables the `telegram@claude-plugins-official` plugin.
The bot token and access list live outside the repo in
`~/.claude/channels/telegram/`. Start a session with
`claude --channels plugin:telegram@claude-plugins-official`, and run only one
such session at a time: two bots polling the same token knock each other off.

## Layout

```
.mcp.json                MCP servers for Claude Code
.claude/settings.json    Telegram plugin (skills go in .claude/skills/)
src/fitness_aggregator/  launchers, config, Hevy client and MCP server
scripts/                 auth and shell helpers
state/                   sessions, tokens, caches, logs (gitignored, 0700)
```
