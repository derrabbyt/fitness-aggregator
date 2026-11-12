"""Proof of concept: estimate sleep from phone use.

An iPhone automation pings POST /api/phone-ping whenever an app is closed. The
longest stretch without pings in a night window is taken as sleep: from the last
ping before it to the first ping after it. Brief phone checks at night (pings
within MERGE_WAKE) join the parts on either side. "Phone untouched" is not the
same as asleep (reading in bed, lying awake), so this is an estimate.

Pings: state/phone_pings/pings.jsonl, one {"t": ISO time, "app": ...} per line,
pruned to KEEP_DAYS. Nothing but the web UI (via /api/sleep) reads them.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from fastapi import APIRouter, Request

from .config import STATE
from .health_inbox import check_token

PINGS = STATE / "phone_pings" / "pings.jsonl"
KEEP_DAYS = 60
WINDOW_FROM = datetime.time(18, 0)  # the evening before the date
WINDOW_TO = datetime.time(14, 0)  # on the date
CORE_FROM, CORE_TO = datetime.time(0, 0), datetime.time(6, 0)  # the sleep gap must overlap this
MIN_SLEEP = datetime.timedelta(hours=3)  # longest gap must be at least this
MERGE_WAKE = datetime.timedelta(minutes=60)  # a phone check at night up to this long ...
MIN_PART = datetime.timedelta(minutes=90)  # ... joins a neighbouring gap at least this long
CHECK_COST = datetime.timedelta(minutes=5)  # awake time counted per interruption besides its span
CHECKS_FROM, CHECKS_TO = datetime.time(21, 0), datetime.time(5, 0)  # only checks in this span join gaps (a morning routine ends the night; the user wakes ~05:00)

router = APIRouter()


def _now() -> datetime.datetime:
    return datetime.datetime.now().astimezone()


def _load() -> list[dict[str, Any]]:
    if not PINGS.exists():
        return []
    out = []
    for line in PINGS.read_text().splitlines():
        try:
            row = json.loads(line)
            row["t"] = datetime.datetime.fromisoformat(row["t"])
            out.append(row)
        except (ValueError, KeyError, TypeError):
            continue
    return out


@router.post("/api/phone-ping")
async def ping(request: Request) -> dict[str, Any]:
    check_token(request)
    app = None
    body = await request.body()
    if body:
        try:
            doc = json.loads(body)
            if isinstance(doc, dict) and doc.get("app") is not None:
                app = str(doc["app"])[:100]
        except ValueError:
            app = body[:100].decode("utf-8", "replace").strip() or None
    now = _now()
    PINGS.parent.mkdir(parents=True, exist_ok=True)
    with PINGS.open("a") as f:
        f.write(json.dumps({"t": now.isoformat(timespec="seconds"), "app": app}) + "\n")
    _prune(now)
    return {"ok": True, "t": now.isoformat(timespec="seconds")}


def _prune(now: datetime.datetime) -> None:
    """Drop pings older than KEEP_DAYS (only rewrites when the oldest is too old)."""
    rows = _load()
    cutoff = now - datetime.timedelta(days=KEEP_DAYS)
    if rows and rows[0]["t"] < cutoff:
        keep = [r for r in rows if r["t"] >= cutoff]
        PINGS.write_text("".join(json.dumps({"t": r["t"].isoformat(timespec="seconds"), "app": r.get("app")}) + "\n" for r in keep))


@router.get("/api/phone-pings")
async def recent(request: Request, hours: int = 36) -> list[dict[str, Any]]:
    check_token(request)
    since = _now() - datetime.timedelta(hours=hours)
    return [{"t": r["t"].isoformat(timespec="seconds"), "app": r.get("app")} for r in _load() if r["t"] >= since]


def ping_times() -> list[datetime.datetime]:
    """Every stored ping's time (read once for several nights)."""
    return [r["t"] for r in _load()]


def estimate(date: datetime.date, times: list[datetime.datetime] | None = None) -> dict[str, Any] | None:
    """Sleep for the night ending on `date`, from ping times (sorted or not)."""
    if times is None:
        times = ping_times()
    tz = _now().tzinfo
    start = datetime.datetime.combine(date - datetime.timedelta(days=1), WINDOW_FROM, tz)
    end = datetime.datetime.combine(date, WINDOW_TO, tz)
    ts = sorted(t for t in times if start <= t <= end)
    if len(ts) < 2:
        return None
    gaps = [(a, b) for a, b in zip(ts, ts[1:])]
    core_from = datetime.datetime.combine(date, CORE_FROM, tz)
    core_to = datetime.datetime.combine(date, CORE_TO, tz)
    night = [k for k in range(len(gaps)) if gaps[k][0] < core_to and gaps[k][1] > core_from]
    if not night:
        return None
    i = max(night, key=lambda k: gaps[k][1] - gaps[k][0])
    if gaps[i][1] - gaps[i][0] < MIN_SLEEP:
        return None
    lo = hi = i
    awake = datetime.timedelta()
    interruptions = 0
    # Join neighbouring gaps across brief phone checks: walk outwards over the
    # short gaps (the check) until a long-enough gap, as long as the check stays short.
    for step in (1, -1):
        k = hi if step == 1 else lo
        while True:
            j = k + step
            check_start = gaps[k][1] if step == 1 else gaps[k][0]
            while 0 <= j < len(gaps) and gaps[j][1] - gaps[j][0] < MIN_PART:
                j += step
            if not 0 <= j < len(gaps):
                break
            check_end = gaps[j][0] if step == 1 else gaps[j][1]
            span = abs(check_end - check_start)
            at = min(check_start, check_end).timetz().replace(tzinfo=None)
            if span > MERGE_WAKE or not (at >= CHECKS_FROM or at < CHECKS_TO):
                break
            awake += span + CHECK_COST
            interruptions += 1
            k = j
        if step == 1:
            hi = k
        else:
            lo = k
    sleep_start, sleep_end = gaps[lo][0], gaps[hi][1]
    in_bed = sleep_end - sleep_start
    return {
        "sleepStart": sleep_start.isoformat(timespec="minutes"),
        "sleepEnd": sleep_end.isoformat(timespec="minutes"),
        "inBed": round(in_bed.total_seconds() / 3600, 2),
        "asleep": round(max(in_bed - awake, datetime.timedelta()).total_seconds() / 3600, 2),
        "interruptions": interruptions,
        "pings": len(ts),
    }
