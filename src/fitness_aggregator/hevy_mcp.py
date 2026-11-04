"""Read-only MCP server for Hevy workouts (stdio)."""

import logging
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import hevy

logging.basicConfig(level=logging.WARNING)  # stdout belongs to the MCP protocol
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


@mcp.tool()
def hevy_get_account() -> dict:
    """The connected Hevy account: username and profile basics."""
    with hevy.client() as c:
        account = c.users.get_account()
    return {k: account.get(k) for k in ("username", "id", "email", "created_at") if k in account}


@mcp.tool()
def hevy_list_workouts(limit: int = 5, offset: int = 0) -> dict:
    """Most recent Hevy workouts first, with exercises and sets.

    limit: how many workouts (1-50, default 5). offset: skip this many of the newest.
    Times are local ISO timestamps.
    """
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


@mcp.tool()
def hevy_get_workout(workout_id: str) -> dict:
    """One Hevy workout by id (from hevy_list_workouts), with exercises and sets."""
    with hevy.client() as c:
        return _summary(c.workouts.get(workout_id))


def main() -> None:
    mcp.run()
