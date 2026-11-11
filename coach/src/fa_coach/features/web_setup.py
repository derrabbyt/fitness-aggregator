"""The web page's Setup tab (coach-web ticket 10): the `setup` view lists the
sections, each with a one-line summary. The envelope says whether a phase is
active and whether a phase setup is open in Telegram; every section is a
part in its own module with its own detail view and edit commands:

    @registry.view_part("setup", "<key>", schema="web_setup_summary", order=...)
    def summary(coach, query, now): return {"summary": "..."}
    @registry.view("setup/<key>", schema="web_setup_<key>")
    @registry.web_command("setup/<key>")

So adding a section means adding a module (and a schema), not editing this
one. The frontend shows a section without a part as "coming soon".

Edits run the chat tools (`run_tool`): the tool's input schema, then the
tool itself, so values are validated the same way as in chat and a refusal
comes back as the same reason (HTTP 400). Nothing here changes targets, the
phase or the MFP goal directly: calibration values only become a proposal
(`propose_change`) approved in Telegram, and starting a phase stays there.
"""

import datetime
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .. import phases, views
from ..ask import ToolError
from ..registry import registry

NO_PHASE = "No phase is active. Start one in Telegram with “start reverse”."
SETUP_OPEN = "A phase setup is open in Telegram. Finish or cancel it there first."


@registry.view("setup", schema="web_setup")
def setup(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    return {"phase_active": phases.active(coach) is not None, "setup_open": phases.open_setup(coach) is not None}


# --- helpers for the section modules -------------------------------------------------


def editable(coach) -> bool:
    """Whether setup values can be edited from the web: a phase is active and
    no phase setup is open (chat would record the value into that setup)."""
    return phases.active(coach) is not None and phases.open_setup(coach) is None


def require_editable(coach) -> dict[str, Any]:
    """The active phase, or a 409 saying why nothing can be edited now."""
    if phases.open_setup(coach) is not None:
        raise views.WebError(409, SETUP_OPEN)
    phase = phases.active(coach)
    if phase is None:
        raise views.WebError(409, NO_PHASE)
    return phase


async def run_tool(coach, name: str, args: dict[str, Any], now: datetime.datetime) -> Any:
    """Run the chat tool `name` as the model's call would: its input schema
    first, then the tool. A refusal becomes a 400 with the tool's reason."""
    tool = coach.registry.tools[name]
    problems = [f"{'/'.join(map(str, e.absolute_path)) or 'input'}: {e.message}"
                for e in Draft202012Validator(tool.input_schema, format_checker=FormatChecker()).iter_errors(args)]
    if problems:
        raise views.WebError(400, "; ".join(problems))
    try:
        return await tool.fn(coach, args, now)
    except ToolError as exc:
        raise views.WebError(400, str(exc)) from None


def field(body: dict[str, Any], key: str) -> Any:
    """A required field of a command's body (400 when it's missing)."""
    if key not in body:
        raise views.WebError(400, f"{key} is missing.")
    return body[key]


def setup_range(coach, key: str) -> dict[str, Any]:
    """{min, max} of a phase-setup value from phase_setup.schema.json (an
    exclusive minimum as `min_exclusive`)."""
    props = coach.skills.schema("phase_setup")["properties"]
    rule = props["logistics"]["properties"][key.split(".", 1)[1]] if key.startswith("logistics.") else props[key]
    out: dict[str, Any] = {"min": rule.get("minimum", rule.get("exclusiveMinimum")), "max": rule.get("maximum")}
    if "exclusiveMinimum" in rule:
        out["min_exclusive"] = True
    return out

