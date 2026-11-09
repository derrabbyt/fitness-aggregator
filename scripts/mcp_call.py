"""Call the api's MCP tools (:8001) from the shell.

    docker compose exec api python scripts/mcp_call.py mfp --list
    docker compose exec api python scripts/mcp_call.py mfp '[["fitness_get_day", {}]]'
    docker compose exec api python scripts/mcp_call.py hevy '[["hevy_list_workouts", {"limit": 3}]]'

Goes through the running api (FA_TOOLS_URL, default http://127.0.0.1:8001), so
the api stays the only user of the MFP session.

Prints one JSON object per call. MFP writes are not idempotent (every
fitness_log_food adds an entry), so never re-run a write to "retry" it.
"""

import asyncio
import json
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

SERVERS = ("mfp", "hevy")
TOOLS_URL = os.environ.get("FA_TOOLS_URL", "http://127.0.0.1:8001")


async def main(server: str, arg: str) -> None:
    async with streamable_http_client(f"{TOOLS_URL}/{server}/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if arg == "--list":
                for t in (await s.list_tools()).tools:
                    print(f"{t.name}: {(t.description or '').splitlines()[0] if t.description else ''}")
                return
            for tool, args in json.loads(arg):
                res = await asyncio.wait_for(s.call_tool(tool, args), 180)
                text = "\n".join(c.text for c in res.content if hasattr(c, "text"))
                print(json.dumps({"tool": tool, "isError": res.isError, "text": text}))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in SERVERS:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
