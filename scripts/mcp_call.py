"""Call tools on this repo's MCP servers from the shell.

    uv run scripts/mcp_call.py mfp '[["fitness_get_day", {}]]'
    uv run scripts/mcp_call.py hevy '[["hevy_list_workouts", {"limit": 3}]]'
    uv run scripts/mcp_call.py mfp --list

Prints one JSON object per call. MFP writes are not idempotent (every
fitness_log_food adds an entry), so never re-run a write to "retry" it.
"""

import asyncio
import json
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
SERVERS = {"mfp": "fa-mfp-mcp", "hevy": "fa-hevy-mcp"}


async def main(server: str, arg: str) -> None:
    exe = shutil.which(SERVERS[server], path=str(Path(sys.executable).parent))
    params = StdioServerParameters(command=exe, args=[], cwd=str(ROOT))
    log_dir = ROOT / "state" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / f"{server}.stderr.log", "w") as log:
        async with stdio_client(params, errlog=log) as (r, w):
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
