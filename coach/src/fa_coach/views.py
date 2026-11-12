"""Read models and edits for the web page (coach-web spec, ADR 0001).

A read model is a view registered with `@registry.view(name, schema=...)`,
plus the parts other modules add to it with `@registry.view_part(view, key,
schema=...)`. Each is computed from stored data only, "as of" the day or
week it is asked for; nothing extra is stored. Edits are
`@registry.web_command(name)` and go through the same code as the chat
tools. The Coach core exposes them as `coach.view`, `coach.refresh` and
`coach.command`; `web_adapter.py` maps them onto HTTP.

Views must only read: the web adapter runs them outside its lock on purpose
(see `web_adapter.py`), so a view computed during a sync may mix data from
before and after the sync's writes until the page reloads or refreshes.

Every view and part has a JSON schema in coach-skills/schemas
(`web_<name>.schema.json`): the API contract the frontend's types follow.
`errors(coach, name, data)` checks a rendered view against its schema and
each part against its own (the tests do this for every view).

Shared helpers for views: `day(query, now)` (the `?day=` parameter, default
today, never in the future) and `freshness(coach, now)`; for web commands:
`field(body, key)` (a required field) and `run_tool(coach, name, args, now)`
(a chat tool, validated and refused the way chat does it).
"""

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator, FormatChecker

from . import history
from .ask import ToolError

if TYPE_CHECKING:
    from .core import Coach

Date = datetime.date


class WebError(Exception):
    """A request the coach refuses: `status` is the HTTP status, `message`
    the plain reason shown on the page (the same words chat would use)."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def render(coach: "Coach", name: str, query: Mapping[str, str], now: datetime.datetime) -> dict[str, Any]:
    view = coach.registry.views.get(name)
    if view is None:
        raise WebError(404, f"There is no view {name!r}.")
    query = dict(query)
    data = view.fn(coach, query, now)
    for part in coach.registry.view_parts(name):
        data[part.key] = part.fn(coach, query, now)
    return data


async def command(coach: "Coach", name: str, body: Mapping[str, Any], now: datetime.datetime) -> Any:
    fn = coach.registry.web_commands.get(name)
    if fn is None:
        raise WebError(404, f"There is no command {name!r}.")
    return await fn(coach, dict(body), now)


def errors(coach: "Coach", name: str, data: dict[str, Any]) -> list[str]:
    """Schema errors of a rendered view: the view's own schema, then each
    part against its schema (prefixed with its key)."""
    view = coach.registry.views[name]
    found = coach.skills.errors(data, view.schema)
    for part in coach.registry.view_parts(name):
        if part.key not in data:
            found.append(f"{part.key}: missing")
            continue
        found += [f"{part.key}/{e}" for e in coach.skills.errors(data[part.key], part.schema)]
    return found


# --- shared helpers -------------------------------------------------------------------


def day(query: Mapping[str, str], now: datetime.datetime) -> Date:
    """`?day=YYYY-MM-DD`, default today. A future day is refused."""
    raw = query.get("day")
    if not raw:
        return now.date()
    try:
        value = Date.fromisoformat(raw)
    except ValueError:
        raise WebError(400, f"{raw!r} is not a date (YYYY-MM-DD).") from None
    if value > now.date():
        raise WebError(400, "That day hasn't started yet.")
    return value


def freshness(coach: "Coach", now: datetime.datetime) -> dict[str, Any]:
    """{last_sync_at, age_hours, stale}: stale when the older source's last
    successful sync is missing or older than `data.sync_max_age_hours`."""
    fresh = history.freshness(coach.db, now, coach.skills.params()["data"]["sync_max_age_hours"])
    return {"last_sync_at": fresh["last_sync_at"], "age_hours": fresh["age_hours"], "stale": not fresh["fresh"]}


async def run_tool(coach, name: str, args: dict[str, Any], now: datetime.datetime) -> Any:
    """Run the chat tool `name` as the model's call would: its input schema
    first, then the tool. A refusal becomes a 400 with the tool's reason."""
    tool = coach.registry.tools[name]
    problems = [f"{'/'.join(map(str, e.absolute_path)) or 'input'}: {e.message}"
                for e in Draft202012Validator(tool.input_schema, format_checker=FormatChecker()).iter_errors(args)]
    if problems:
        raise WebError(400, "; ".join(problems))
    try:
        return await tool.fn(coach, args, now)
    except ToolError as exc:
        raise WebError(400, str(exc)) from None


def field(body: dict[str, Any], key: str) -> Any:
    """A required field of a command's body (400 when it's missing)."""
    if key not in body:
        raise WebError(400, f"{key} is missing.")
    return body[key]
