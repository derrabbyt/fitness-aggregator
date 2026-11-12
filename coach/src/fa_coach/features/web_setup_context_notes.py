"""Setup › Context notes (coach-web ticket 12): every context note with its
dates and tags, newest first; adding and deleting run the chat tools:

    POST setup/context-notes/add    {text, applies_from, applies_to?, tags, suggest_unusable?, exercise_id?}
    POST setup/context-notes/delete {id}

A note added here is stored like one from chat: `text` is the user's words
(chat stores the message itself), the rest goes through add_context_note's
input schema (`suggest_unusable` defaults to "no"). Neither needs an active
phase. Both return the section.
"""

import datetime
from typing import Any

from ..registry import registry
from . import context_notes, web_setup

_OPTIONAL = ("applies_to", "exercise_id", "follow_up_question")


def _all(coach) -> list[dict[str, Any]]:
    notes = context_notes.between(coach, datetime.date.min, datetime.date.max)
    return sorted(notes, key=lambda n: (n["applies_from"], n["created_at"], n["id"]), reverse=True)


@registry.view_part("setup", "context_notes", schema="web_setup_summary", order=60)
def summary(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    total = len(_all(coach))
    if not total:
        return {"summary": "No notes yet"}
    today = len(context_notes.between(coach, now.date(), now.date()))
    applies = "none apply today" if not today else f"{today} appl{'ies' if today == 1 else 'y'} today"
    return {"summary": f"{total} note{'' if total == 1 else 's'} · {applies}"}


@registry.view("setup/context-notes", schema="web_setup_context_notes")
def notes(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    tags = coach.skills.schema("context_note")["properties"]["tags"]["items"]["enum"]
    return {"today": now.date().isoformat(), "tag_options": list(tags), "notes": _all(coach)}


@registry.web_command("setup/context-notes/add")
async def add(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    text = web_setup.field(body, "text")
    args = {"applies_from": web_setup.field(body, "applies_from"), "tags": web_setup.field(body, "tags"),
            "suggest_unusable": body.get("suggest_unusable") or "no"}
    args.update({k: body[k] for k in _OPTIONAL if body.get(k) is not None})
    coach.current_message = text.strip() if isinstance(text, str) else None
    try:
        await web_setup.run_tool(coach, "add_context_note", args, now)
    finally:
        coach.current_message = None
    return notes(coach, {}, now)


@registry.web_command("setup/context-notes/delete")
async def delete(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    await web_setup.run_tool(coach, "delete_context_note", {"id": web_setup.field(body, "id")}, now)
    return notes(coach, {}, now)
