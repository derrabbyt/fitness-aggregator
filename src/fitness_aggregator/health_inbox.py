"""Proof of concept: receive Apple Health exports (e.g. Marrow / Health Auto
Export, "Gesundheitsmetriken" / Health Metrics JSON) and keep them unchanged in
state/health_inbox/ to see what arrives. No parsing, nothing else reads them.

POST /api/health-data   any body; stored as-is with a small .meta.json beside it
GET  /api/health-data   lists what arrived (newest first) with a shallow summary

If HEALTH_INGEST_TOKEN is set, both need it: header `X-Token: <token>`,
`Authorization: Bearer <token>`, or `?token=<token>`.
"""

from __future__ import annotations

import datetime
import hmac
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .config import STATE

INBOX = STATE / "health_inbox"
MAX_BYTES = 50 * 1024 * 1024
router = APIRouter()
logger = logging.getLogger("fa-api.health_inbox")


def check_token(request: Request) -> None:
    expected = os.environ.get("HEALTH_INGEST_TOKEN", "")
    if not expected:
        return
    auth = request.headers.get("authorization", "")
    given = (
        request.headers.get("x-token")
        or (auth[7:] if auth.lower().startswith("bearer ") else "")
        or request.query_params.get("token", "")
    )
    if not hmac.compare_digest(given.encode(), expected.encode()):
        # Says how a token arrived (never its value) so a client setup can be debugged.
        via = ("x-token header" if request.headers.get("x-token") else
               "authorization header" if auth else
               "token query" if request.query_params.get("token") else None)
        detail = (f"wrong token via {via} ({len(given)} chars, expected {len(expected)})" if via
                  else f"no token; headers seen: {sorted(request.headers.keys())}")
        logger.info("health-data 401: %s", detail)
        raise HTTPException(401, detail)


def _summary(body: bytes) -> dict[str, Any]:
    """Shallow look at the payload: top-level keys and, for Health Auto
    Export-style payloads, metric names with point counts."""
    try:
        doc = json.loads(body)
    except ValueError:
        return {"json": False}
    out: dict[str, Any] = {"json": True}
    if isinstance(doc, dict):
        out["keys"] = sorted(doc)[:30]
        data = doc.get("data")
        if isinstance(data, dict):
            out["data_keys"] = sorted(data)[:30]
            metrics = data.get("metrics")
            if isinstance(metrics, list):
                out["metrics"] = {
                    str(m.get("name")): len(m.get("data") or []) for m in metrics if isinstance(m, dict)
                }
            workouts = data.get("workouts")
            if isinstance(workouts, list):
                out["workouts"] = len(workouts)
    elif isinstance(doc, list):
        out["list_len"] = len(doc)
    return out


@router.post("/api/health-data")
async def receive(request: Request) -> dict[str, Any]:
    check_token(request)
    body = await request.body()
    if len(body) > MAX_BYTES:
        raise HTTPException(413, f"body over {MAX_BYTES // (1024 * 1024)} MB")
    INBOX.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    kind = (request.headers.get("content-type") or "").split(";")[0].strip()
    ext = "json" if "json" in kind or body[:1] in (b"{", b"[") else "bin"
    path = INBOX / f"{stamp}.{ext}"
    path.write_bytes(body)
    summary = _summary(body)
    meta = {
        "received_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "content_type": kind,
        "bytes": len(body),
        "user_agent": request.headers.get("user-agent"),
        "query": {k: v for k, v in request.query_params.items() if k != "token"},
        "summary": summary,
    }
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return {"stored": path.name, "bytes": len(body), "summary": summary}


@router.get("/api/sleep")
async def sleep(date: str) -> dict[str, Any]:
    """The night Marrow dates `date` (its `sleep_analysis` entry), for the web UI.
    Exports are incremental, so every stored file is read; a later file wins."""
    try:
        day = datetime.date.fromisoformat(date)
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")
    from .phone_sleep import estimate  # phone-use estimate (pings), shown next to Health's entry

    phone = estimate(day)
    night = None
    for path in sorted(INBOX.glob("*.json")) if INBOX.exists() else []:
        if path.name.endswith(".meta.json"):
            continue
        try:
            metrics = json.loads(path.read_bytes())["data"]["metrics"]
        except (ValueError, KeyError, TypeError):
            continue
        for m in metrics if isinstance(metrics, list) else []:
            if not isinstance(m, dict) or m.get("name") != "sleep_analysis":
                continue
            for point in m.get("data") or []:
                if isinstance(point, dict) and str(point.get("date", ""))[:10] == date:
                    night = point
    keys = ("asleep", "inBed", "totalSleep", "sleepStart", "sleepEnd", "core", "deep", "rem", "awake")
    health = {k: night[k] for k in keys if k in night} if night is not None else None
    return {"date": date, "night": health, "phone": phone}


@router.get("/api/health-data")
async def inbox(request: Request) -> list[dict[str, Any]]:
    check_token(request)
    if not INBOX.exists():
        return []
    out = []
    for meta in sorted(INBOX.glob("*.meta.json"), reverse=True)[:50]:
        try:
            out.append({"file": meta.name.replace(".meta.json", ""), **json.loads(meta.read_text())})
        except ValueError:
            continue
    return out
