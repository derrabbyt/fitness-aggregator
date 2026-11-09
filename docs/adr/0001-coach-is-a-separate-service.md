# The coach is a separate service with its own bot and database

The coach runs as its own service (`coach`) next to the food bot, polls its own Telegram bot token, and keeps its own SQLite database in `state/coach/`. Like the food bot, it reaches MyFitnessPal and Hevy only through `fa-api`, which stays the single owner of the MFP session. We chose this over adding the coach to `fa-bot` so the two bots fail, restart and get tested independently, and each bot token has exactly one poller.

## Consequences

- The coach is the only client that writes the MFP calorie goal, through a `fa-api` tool that only its code calls after the user approves a change; the food bot and the coach model never see that tool.
- The coach is the only process that opens `coach.db`. The web UI reaches coach data through a small HTTP API on the coach service, which `fa-api` proxies under `/api/coach/`, so edits from the web go through the same validation as edits from chat.
- Proposals can be approved from Telegram or the web page; both use one atomic claim in the coach, so an approval applies once whichever side wins. The web UI has no login: access control is the tailnet (`FA_BIND`).
