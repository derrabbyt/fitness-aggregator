"""Context notes: the user's own dated notes (sick, travel, camp week,
creatine, knee hurts), stored in the user's words with dates and tags
(context_note.schema.json). Every later decision reads them; a `sport_load`
tag marks a heavy week.

`between(coach, start, end)` is the read API for facts; the model gets
`add_context_note`, `get_context_notes` and `delete_context_note`.
"""

import datetime
import json
import secrets
from typing import Any

from ..ask import ToolError
from ..registry import registry
from ..skills import SkillsPackage

_FIELDS = ("id", "created_at", "text", "applies_from", "applies_to", "tags", "exercise_id", "suggest_unusable", "follow_up_question")
_SET_BY_CODE = ("id", "created_at", "text")


def _input_schema() -> dict[str, Any]:
    """add_context_note's input: the context_note schema without the fields
    code fills in (one source for tags and the rest)."""
    note = SkillsPackage().schema("context_note")
    properties = {k: v for k, v in note["properties"].items() if k not in _SET_BY_CODE}
    return {
        "type": "object",
        "properties": properties,
        "required": [k for k in note["required"] if k not in _SET_BY_CODE and k != "applies_to"],
        "additionalProperties": False,
    }


def between(coach, start: datetime.date, end: datetime.date) -> list[dict[str, Any]]:
    """Notes that apply to any day from `start` to `end` (inclusive). A note
    without `applies_to` is ongoing from `applies_from`. Ordered by start."""
    rows = coach.db.all(
        "SELECT * FROM context_notes WHERE applies_from <= ? AND COALESCE(applies_to, '9999-12-31') >= ?"
        " ORDER BY applies_from, created_at, id",
        (end.isoformat(), start.isoformat()),
    )
    return [_note(row) for row in rows]


def _note(row) -> dict[str, Any]:
    note = {key: row[key] for key in _FIELDS}
    note["tags"] = json.loads(note["tags"])
    return note


@registry.tool(
    "add_context_note",
    "Store context the user gave (illness, travel, a heavy sport week, a supplement, pain, a skipped session …) "
    "as a dated, tagged note. Code stores the user's message itself as the note's text. applies_to: the last day "
    "it concerns; the same as applies_from for a single day; omit or null for something ongoing. Tag a heavy "
    "week (camp, tournament, double sessions) with sport_load. Returns the stored note.",
    _input_schema(),
)
async def add_context_note(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    if not coach.current_message:
        raise ToolError("a context note needs a message from the user")
    applies_from = args["applies_from"]
    applies_to = args.get("applies_to")
    if applies_to is not None and applies_to < applies_from:
        raise ToolError("applies_to is before applies_from")
    note = {
        "id": f"n_{secrets.token_hex(4)}",
        "created_at": now.isoformat(timespec="seconds"),
        "text": coach.current_message,
        "applies_from": applies_from,
        "applies_to": applies_to,
        "tags": list(dict.fromkeys(args["tags"])),
        "exercise_id": args.get("exercise_id"),
        "suggest_unusable": args["suggest_unusable"],
        "follow_up_question": args.get("follow_up_question"),
    }
    coach.db.execute(
        f"INSERT INTO context_notes ({', '.join(_FIELDS)}) VALUES ({', '.join('?' * len(_FIELDS))})",
        tuple(json.dumps(note[k]) if k == "tags" else note[k] for k in _FIELDS),
    )
    return note


@registry.tool(
    "get_context_notes",
    "Context notes that apply to any day from `from` to `to` (inclusive, ISO dates).",
    {
        "type": "object",
        "properties": {"from": {"type": "string", "format": "date"}, "to": {"type": "string", "format": "date"}},
        "required": ["from", "to"],
        "additionalProperties": False,
    },
)
async def get_context_notes(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    start, end = datetime.date.fromisoformat(args["from"]), datetime.date.fromisoformat(args["to"])
    if end < start:
        raise ToolError("`to` is before `from`")
    return {"notes": between(coach, start, end)}


@registry.tool(
    "delete_context_note",
    "Delete a context note the user says is wrong (e.g. a week tagged sport_load that wasn't heavy after all). "
    "Find its id with get_context_notes first.",
    {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"], "additionalProperties": False},
)
async def delete_context_note(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    if coach.db.execute("DELETE FROM context_notes WHERE id = ?", (args["id"],)).rowcount != 1:
        raise ToolError(f"no context note with id {args['id']!r}")
    return {"deleted": args["id"]}
