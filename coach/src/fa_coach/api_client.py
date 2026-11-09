"""The real api client: fa-api over HTTP, the coach's only way to MFP and Hevy.

Sync reads come from the api's REST endpoints (`api_url`, ticket 02); the
MFP goal is set through the `fitness_set_goal` MCP tool (`tools_url`, ticket
06): sent once, read back once, never retried.
"""

import datetime
from typing import Any

import httpx

# The api reads MFP day by day (two requests per day), so a 4-week chunk can
# take a few minutes.
READ_TIMEOUT = httpx.Timeout(600.0, connect=10.0)


class HttpApiClient:
    def __init__(self, api_url: str, tools_url: str):
        self.api_url = api_url.rstrip("/")
        self.tools_url = tools_url.rstrip("/")

    async def mfp_days(self, start: datetime.date, end: datetime.date) -> list[dict[str, Any]]:
        return (await self._get("/api/sync/mfp", start, end))["days"]

    async def hevy_sessions(self, start: datetime.date, end: datetime.date) -> list[dict[str, Any]]:
        return (await self._get("/api/sync/hevy", start, end))["sessions"]

    async def _get(self, path: str, start: datetime.date, end: datetime.date) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=READ_TIMEOUT) as client:
            resp = await client.get(self.api_url + path, params={"start": start.isoformat(), "end": end.isoformat()})
        if resp.status_code >= 400:
            detail = None
            if resp.headers.get("content-type", "").startswith("application/json"):
                detail = resp.json().get("detail")
            raise RuntimeError(f"api {path}: {resp.status_code} {detail or resp.reason_phrase}")
        return resp.json()
