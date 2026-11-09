"""The real api client: fa-api over HTTP, the coach's only way to MFP and Hevy.

Sync reads come from the api's REST endpoints (`api_url`, ticket 02); the
MFP goal is set and read through the `fitness_set_goal` / `fitness_get_goal`
MCP tools (`tools_url`): one POST each, never retried (fa_coach/mfp_goal.py
decides what the outcome means).
"""

import datetime
import json
from typing import Any

import httpx

# The api reads MFP day by day (two requests per day), so a 4-week chunk can
# take a few minutes.
READ_TIMEOUT = httpx.Timeout(600.0, connect=10.0)
# The goal write is a read, one POST and a read-back on the api's side.
TOOL_TIMEOUT = httpx.Timeout(180.0, connect=10.0)


def _goal(stored: dict[str, Any] | None) -> dict[str, Any] | None:
    """The api's {calories, protein, carbs, fat} as the coach's goal shape."""
    if not stored:
        return None
    return {"kcal": stored.get("calories"), "protein_g": stored.get("protein"), "carbs_g": stored.get("carbs"),
            "fat_g": stored.get("fat")}


class HttpApiClient:
    def __init__(self, api_url: str, tools_url: str):
        self.api_url = api_url.rstrip("/")
        self.tools_url = tools_url.rstrip("/")

    async def mfp_days(self, start: datetime.date, end: datetime.date) -> list[dict[str, Any]]:
        return (await self._get("/api/sync/mfp", start, end))["days"]

    async def hevy_sessions(self, start: datetime.date, end: datetime.date) -> list[dict[str, Any]]:
        return (await self._get("/api/sync/hevy", start, end))["sessions"]

    async def set_mfp_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        reply = await self._tool("fitness_set_goal", {"calories": goal["kcal"], "protein": goal["protein_g"],
                                                      "carbs": goal["carbs_g"], "fat": goal["fat_g"]})
        return {"write": reply.get("write"), "stored": _goal(reply.get("stored")), "error": reply.get("error")}

    async def mfp_goal(self) -> dict[str, Any] | None:
        return _goal((await self._tool("fitness_get_goal", {}))["goal"])

    async def _tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """One MCP `tools/call` as a single JSON-RPC POST to the stateless
        tools endpoint. Deliberately not the MCP client session: one request,
        no initialize round trip, and nothing that could resend it (httpx
        never retries a request; `retries=0` only concerns connecting)."""
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
        transport = httpx.AsyncHTTPTransport(retries=0)
        async with httpx.AsyncClient(timeout=TOOL_TIMEOUT, transport=transport) as client:
            resp = await client.post(self.tools_url + "/mfp/mcp", json=body,
                                     headers={"Accept": "application/json, text/event-stream"})
        if resp.status_code >= 400:
            raise RuntimeError(f"api {name}: {resp.status_code} {resp.reason_phrase}")
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"api {name}: {data['error'].get('message')}")
        result = data["result"]
        text = "\n".join(c.get("text", "") for c in result.get("content") or [] if c.get("type") == "text")
        if result.get("isError"):
            raise RuntimeError(f"api {name}: {text.strip()[:200]}")
        return json.loads(text)

    async def _get(self, path: str, start: datetime.date, end: datetime.date) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=READ_TIMEOUT) as client:
            resp = await client.get(self.api_url + path, params={"start": start.isoformat(), "end": end.isoformat()})
        if resp.status_code >= 400:
            detail = None
            if resp.headers.get("content-type", "").startswith("application/json"):
                detail = resp.json().get("detail")
            raise RuntimeError(f"api {path}: {resp.status_code} {detail or resp.reason_phrase}")
        return resp.json()
