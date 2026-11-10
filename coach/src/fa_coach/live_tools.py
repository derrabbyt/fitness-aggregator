"""Live read-only MFP and Hevy tools for the coach model (ticket 16).

The model can look things up in MyFitnessPal and Hevy ("what did I eat on
Tuesday?", "what did I do on pull-ups last week?") through the api's MCP
tools (:8001), via the coach's api client: fa-api stays the only MFP session
owner. Only the tools in `READ_TOOLS` are ever offered or called. It must
stay read-only: no `fitness_log_*`, `fitness_delete_*`, `fitness_modify_food`,
`fitness_quick_add`, `fitness_clear_food_pin` or `fitness_set_goal` (coach
code sets the goal itself, `mfp_goal.py`); `fitness_draft_food` (the coach
doesn't log food) and `fitness_bulk_export` (huge; the synced data covers it)
are left out too. `tests/test_live_tools.py` checks it by name and pattern.

Definitions come from the api's `tools/list` (so schemas stay in sync),
listed once per server and cached for the process; a server whose listing
failed is retried after `RETRY_AFTER`, and the coach runs without its tools
meanwhile. Registered on the registry by `features/live_tools.py`.
"""

import datetime
import json
import logging
import weakref
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .registry import Tool

if TYPE_CHECKING:
    from .core import Coach

logger = logging.getLogger("fa-coach")

MFP_READ_TOOLS = frozenset({
    "fitness_get_day",
    "fitness_get_activity",
    "fitness_get_exercise",
    "fitness_get_exercise_entries",
    "fitness_get_note",
    "fitness_get_trends",
    "fitness_search_food",
})
HEVY_READ_TOOLS = frozenset({"hevy_get_account", "hevy_list_workouts", "hevy_get_workout"})
SERVERS = {"mfp": MFP_READ_TOOLS, "hevy": HEVY_READ_TOOLS}
READ_TOOLS = MFP_READ_TOOLS | HEVY_READ_TOOLS

RETRY_AFTER = datetime.timedelta(minutes=10)
MAX_RESULT_CHARS = 20_000  # what goes back to the model, as JSON text
NOTE = ("Live read from {source} (lookup only: targets and decisions come from code's facts; "
        "point odd entries out for the user to fix, never change them). ")


def server_of(name: str) -> str | None:
    """The api MCP server ("mfp" / "hevy") an allowed tool lives on, None for
    anything not on the read-only allowlist."""
    return next((server for server, names in SERVERS.items() if name in names), None)


@dataclass
class _Listing:
    tools: dict[str, list[Tool]] = field(default_factory=dict)  # server -> its allowed tools, once listed
    tried: dict[str, datetime.datetime] = field(default_factory=dict)  # server -> last failed listing


_listings: "weakref.WeakKeyDictionary[Coach, _Listing]" = weakref.WeakKeyDictionary()


async def ensure_listed(coach: "Coach", now: datetime.datetime) -> None:
    """List each server's tools once; a failed listing is retried after
    `RETRY_AFTER`."""
    listing = _listings.setdefault(coach, _Listing())
    for server in SERVERS:
        if server in listing.tools:
            continue
        last = listing.tried.get(server)
        if last is not None and now - last < RETRY_AFTER:
            continue
        try:
            listed = await coach.api.list_tools(server)
        except Exception as exc:  # noqa: BLE001 - the coach runs without them for now
            listing.tried[server] = now
            logger.warning("listing the api's %s tools failed (%s); retrying in %s", server, exc, RETRY_AFTER)
            continue
        listing.tools[server] = _allowed(server, listed)
        logger.info("live %s tools: %s", server, ", ".join(t.name for t in listing.tools[server]) or "none")


async def tools(coach: "Coach", now: datetime.datetime) -> list[Tool]:
    await ensure_listed(coach, now)
    listing = _listings[coach]
    return [tool for server in SERVERS for tool in listing.tools.get(server, [])]


def _allowed(server: str, listed: list[dict[str, Any]]) -> list[Tool]:
    found = []
    for item in listed:
        name = item.get("name")
        if name not in SERVERS[server]:
            continue
        schema = item.get("inputSchema") or {"type": "object"}
        description = NOTE.format(source="MyFitnessPal" if server == "mfp" else "Hevy") + (item.get("description") or "")
        found.append(Tool(name, description.strip(), schema, _caller(server, name)))
    return sorted(found, key=lambda t: t.name)


def _caller(server: str, name: str):
    async def call(coach: "Coach", args: dict[str, Any], now: datetime.datetime) -> Any:
        if server_of(name) != server:  # never reached: only allowlisted tools are built
            raise PermissionError(f"{name} is not a live read tool")
        return truncate(await coach.api.read_tool(server, name, args))

    return call


def truncate(result: Any) -> Any:
    """The result unchanged if its JSON fits `MAX_RESULT_CHARS`, else its
    first `MAX_RESULT_CHARS` characters, marked as truncated."""
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    if len(text) <= MAX_RESULT_CHARS:
        return result
    return {"truncated": True, "text": text[:MAX_RESULT_CHARS],
            "note": f"cut to {MAX_RESULT_CHARS} of {len(text)} characters; ask for a narrower range"}
