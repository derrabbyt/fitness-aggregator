"""Read-only MCP server for Hevy workouts: stdio (`fa-hevy-mcp`) or mounted over
HTTP by tools_server. Hevy calls block, so tools run in a worker thread."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import hevy

mcp = FastMCP("hevy")


def _when(ts: Any) -> str | None:
    return datetime.fromtimestamp(ts).isoformat(timespec="minutes") if isinstance(ts, (int, float)) else ts


def _summary(w: dict) -> dict:
    exercises = w.get("exercises") or []
    return {
        "id": w.get("id"),
        "name": w.get("name"),
        "start": _when(w.get("start_time")),
        "end": _when(w.get("end_time")),
        "exercises": [
            {
                "title": e.get("title"),
                "sets": [
                    {k: s.get(k) for k in ("indicator", "weight_kg", "reps", "distance_meters", "duration_seconds", "rpe") if s.get(k) is not None}
                    for s in e.get("sets") or []
                ],
            }
            for e in exercises
        ],
    }


def _account() -> dict:
    with hevy.client() as c:
        account = c.users.get_account()
    return {k: account.get(k) for k in ("username", "id", "email", "created_at") if k in account}


def _list_workouts(limit: int, offset: int) -> dict:
    limit = max(1, min(limit, 50))
    with hevy.client() as c:
        username = c.users.get_account()["username"]
        workouts = []
        for w in c.workouts.iter_paged(username, page_size=hevy.PAGE_SIZE):
            if offset:
                offset -= 1
                continue
            workouts.append(_summary(w))
            if len(workouts) >= limit:
                break
    return {"count": len(workouts), "workouts": workouts}


def _workout(workout_id: str) -> dict:
    with hevy.client() as c:
        return _summary(c.workouts.get(workout_id))


@mcp.tool()
async def hevy_get_account() -> dict:
    """The connected Hevy account: username and profile basics."""
    return await asyncio.to_thread(_account)


@mcp.tool()
async def hevy_list_workouts(limit: int = 5, offset: int = 0) -> dict:
    """Most recent Hevy workouts first, with exercises and sets.

    limit: how many workouts (1-50, default 5). offset: skip this many of the newest.
    Times are local ISO timestamps.
    """
    return await asyncio.to_thread(_list_workouts, limit, offset)


@mcp.tool()
async def hevy_get_workout(workout_id: str) -> dict:
    """One Hevy workout by id (from hevy_list_workouts), with exercises and sets."""
    return await asyncio.to_thread(_workout, workout_id)


def main() -> None:
    logging.basicConfig(level=logging.WARNING)  # stdout belongs to the MCP protocol
    mcp.run()
