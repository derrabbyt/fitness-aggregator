"""`/api/coach/*` passes through to the coach's HTTP API (ADR 0001).

The coach serves the web page's read models and edits from its own process
(the only one that opens coach.db) on the compose network, unpublished.
This process forwards method, path, query and body unchanged and streams
the answer back; it adds nothing coach-specific. Access control is the
tailnet (FA_BIND), as for the rest of the UI.
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

COACH_URL = os.environ.get("FA_COACH_URL", "http://127.0.0.1:8002")
# A refresh syncs MFP and Hevy before it answers.
TIMEOUT = httpx.Timeout(300.0, connect=5.0)
# Hop-by-hop headers (and Host) stay on their own hop.
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade", "host", "content-length"}

router = APIRouter()
_client: httpx.AsyncClient | None = None


def _coach() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=COACH_URL, timeout=TIMEOUT)
    return _client


@router.api_route("/api/coach/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                  include_in_schema=False)
async def coach(path: str, request: Request):
    client = _coach()
    upstream = client.build_request(
        request.method,
        httpx.URL(path=request.url.path, query=request.url.query.encode()),
        headers=[(k, v) for k, v in request.headers.items() if k.lower() not in HOP],
        content=await request.body(),
    )
    try:
        response = await client.send(upstream, stream=True)
    except httpx.HTTPError:
        return JSONResponse({"error": "The coach isn't reachable right now."}, status_code=502)
    return StreamingResponse(
        response.aiter_raw(),
        status_code=response.status_code,
        headers={k: v for k, v in response.headers.items() if k.lower() not in HOP - {"content-length"}},
        background=BackgroundTask(response.aclose),
    )
