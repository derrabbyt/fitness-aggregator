"""Setup › Activity values (coach-web ticket 10): the run discount and the kcal
counted per wrestling and per lifting session. These are calibration values:
a change from the web (`setup/activity` {values}) becomes a
`calibration_change` proposal through chat's `propose_change`, so its card
with approve / reject / counter goes to Telegram and nothing changes until
the user taps Approve there. Out-of-range values are refused with the
guardrail's reason (the blocked proposal is stored, as in chat).
"""

import datetime
from typing import Any

from .. import phases, proposals, views
from ..registry import registry
from . import web_setup

KEYS = phases.CALIBRATION_KEYS
REASON = "Changed on the web page."


@registry.view_part("setup", "activity", schema="web_setup_summary", order=20)
def summary(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    a = phases.params(coach)["activity"]
    run, wrestling, lifting = (a.get(k) for k in KEYS)
    parts = [
        f"Runs {round(run * 100)} %" if run is not None else "Runs not set",
        f"wrestling {wrestling:,g} kcal" if wrestling is not None else "wrestling not set",
        f"lifting {lifting:,g} kcal" if lifting is not None else "lifting not set",
    ]
    pending = _pending(coach)
    return {"summary": " · ".join(parts) + (" · change waiting in Telegram" if pending else "")}


@registry.view("setup/activity", schema="web_setup_activity")
def activity(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    a = phases.params(coach)["activity"]
    return {
        "editable": web_setup.editable(coach),
        "values": {k: {"value": a.get(k), **web_setup.setup_range(coach, k)} for k in KEYS},
        "pending": [_short(p) for p in _pending(coach)],
    }


@registry.web_command("setup/activity")
async def set_activity(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """{values: {run_kcal_discount?, wrestling_kcal_per_session?,
    lifting_kcal_per_session?}}: the changed values become one calibration
    proposal (card to Telegram). Returns {proposal, section}."""
    web_setup.require_editable(coach)
    values = web_setup.field(body, "values")
    if not isinstance(values, dict) or not values:
        raise views.WebError(400, "values must name at least one activity value.")
    current = phases.params(coach)["activity"]
    changed = {k: v for k, v in values.items() if k not in current or current.get(k) != v}
    if not changed:
        raise views.WebError(400, "Those are the current values; nothing to change.")
    result = await web_setup.run_tool(coach, "propose_change", {
        "type": "calibration_change", "new_values": changed, "reason": REASON, "source": "user_request"}, now)
    if result["status"] == "blocked_by_guardrail":
        raise views.WebError(400, " ".join(d["text"] for d in result["guardrail"]["details"]))
    return {"proposal": {**_short(result), "referenced": bool(result.get("referenced"))},
            "section": activity(coach, {}, now)}


def _pending(coach) -> list[dict[str, Any]]:
    return [p for p in proposals.open_proposals(coach) if p["type"] == "calibration_change"]


def _short(p: dict[str, Any]) -> dict[str, Any]:
    return {"id": p["id"], "new_values": p["new_values"], "created_at": p["created_at"],
            "change": proposals.describe_change(p)}
