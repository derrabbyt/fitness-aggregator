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
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .config import STATE

INBOX = STATE / "health_inbox"
MAX_BYTES = 50 * 1024 * 1024
router = APIRouter()


def _check_token(request: Request) -> None:
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
        raise HTTPException(401, "missing or wrong token")


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
    _check_token(request)
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


@router.get("/api/health-data")
async def inbox(request: Request) -> list[dict[str, Any]]:
    _check_token(request)
    if not INBOX.exists():
        return []
    out = []
    for meta in sorted(INBOX.glob("*.meta.json"), reverse=True)[:50]:
        try:
            out.append({"file": meta.name.replace(".meta.json", ""), **json.loads(meta.read_text())})
        except ValueError:
            continue
    return out
