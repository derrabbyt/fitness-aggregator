"""The MFP nutrition goal: `fitness_get_goal` and `fitness_set_goal`, served
as MCP tools on :8001 (tools_server.py). Only coach code calls the set; it
is not in the food bot's read-tool allowlist and the coach model never gets it.

    docker compose exec api python scripts/mcp_call.py mfp '[["fitness_get_goal", {}]]'
    docker compose exec api python scripts/mcp_call.py mfp \
        '[["fitness_set_goal", {"calories": 2300, "protein": 161, "carbs": 251, "fat": 72}]]'

The write is the one MFP's website and python-myfitnesspal's `set_new_goal`
make (POST v2/nutrient-goals: today's goal item with new energy and macros
in the default goal and every weekday goal, valid from today). It is done
here rather than through `set_new_goal`, because that call can't be kept
out of mfp-mcp's `with_session` retry: `run_with_refresh` re-runs the
whole operation after any error that looks like an auth error (401/403,
"token", "session", ...), which would send the POST twice. So:

- the current goal is read through `with_session` (reads may be retried);
- the POST goes out exactly once, outside `with_session`; its outcome is
  "sent" (MFP said ok), "rejected" (MFP answered with an error),
  "uncertain" (no answer: it may or may not have landed) or "not_sent"
  (no MFP session, nothing went out);
- the goal is read back through `with_session` and returned.

Nothing raises after the POST went out, so no caller is tempted to resend.
"""

import asyncio
import copy
import datetime
from typing import Any

from myfitnesspal_mcp import mfp_client
from myfitnesspal_mcp import server as mfp_server
from myfitnesspal_mcp.mfp_web import api_headers

from .log_context import LogContext

GOALS_PATH = "v2/nutrient-goals"
KJ_PER_KCAL = 4.184
MAX_MACRO_EXCESS_KCAL = 25  # MFP raises the calories to the macros' sum when they exceed them


def _url(client) -> str:
    return f"{client.BASE_API_URL.rstrip('/')}/{GOALS_PATH}"


def _read_item(day: datetime.date):
    """Today's goal item (v2/nutrient-goals) or None, through the one MFP session."""

    def op(store, client):
        resp = client.session.get(
            _url(client), params={"date": day.isoformat()},
            headers=api_headers(client, {"Accept": "application/json"}), timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("items") or []
        return items[0] if items else None

    return mfp_server.with_session(LogContext(), op)


def _summary(item: dict | None) -> dict[str, Any] | None:
    if not item:
        return None
    goal = item.get("default_goal") or {}
    energy = goal.get("energy") or {}
    calories = energy.get("value")
    if calories is not None and energy.get("unit") == "kilojoules":
        calories = calories / KJ_PER_KCAL
    return {
        "valid_from": item.get("valid_from"),
        "calories": round(calories) if calories is not None else None,
        "protein": goal.get("protein"),
        "carbs": goal.get("carbohydrates"),
        "fat": goal.get("fat"),
    }


def _payload(current: dict, day: datetime.date, calories: float, protein: float, carbs: float,
             fat: float) -> dict[str, Any]:
    """As python-myfitnesspal's set_new_goal builds it, with absolute grams."""
    item = copy.deepcopy(current)
    for key in ("valid_to", "default_group_id", "updated_at"):
        item.pop(key, None)
    item["valid_from"] = day.isoformat()
    goals = [item["default_goal"], *(item.get("daily_goals") or [])]
    for n, goal in enumerate(goals):
        goal["meal_goals"] = []
        if n:
            goal.pop("group_id", None)
        goal["energy"] = {**(goal.get("energy") or {}), "value": calories, "unit": "calories"}
        goal["carbohydrates"] = carbs
        goal["protein"] = protein
        goal["fat"] = fat
    return {"item": item}


def _post_once(payload: dict[str, Any]) -> tuple[str, str | None]:
    """The single POST. Never retried; exception text isn't passed on (it
    could quote request headers)."""
    try:
        client = mfp_client.get_client()
        headers = api_headers(client, {"Accept": "application/json", "Content-Type": "application/json"})
    except Exception as exc:  # noqa: BLE001
        return "not_sent", f"no MFP session ({type(exc).__name__}); nothing was sent"
    try:
        resp = client.session.post(_url(client), json=payload, headers=headers, timeout=30)
    except Exception as exc:  # noqa: BLE001
        return "uncertain", f"no answer from MFP ({type(exc).__name__}); the goal may or may not be set"
    if resp.ok:
        return "sent", None
    return "rejected", f"MFP answered {resp.status_code}"


async def fitness_get_goal(date: str | None = None) -> dict[str, Any]:
    """The MyFitnessPal nutrition goal in force on a day: calories (kcal) and
    protein / carbs / fat in grams. date: YYYY-MM-DD (default today)."""
    day = datetime.date.fromisoformat(date) if date else datetime.date.today()
    return {"date": day.isoformat(), "goal": _summary(await _read_item(day))}


async def fitness_set_goal(calories: float, protein: float, carbs: float, fat: float) -> dict[str, Any]:
    """Set the MyFitnessPal nutrition goal from today: calories (kcal) and
    protein / carbs / fat in grams, the same on every weekday. Coach code
    only. Sends one request and never retries it; read the result (write,
    stored, matches) and never call it again to "retry": an uncertain write
    may still have landed. A goal refused before sending (out of range, no
    current goal to update, no MFP session) comes back as write "not_sent"."""
    requested = {"calories": round(calories), "protein": protein, "carbs": carbs, "fat": fat}

    def not_sent(why: str) -> dict[str, Any]:
        return {"ok": False, "write": "not_sent", "requested": requested, "stored": None, "matches": None,
                "error": why, "note": "Nothing was sent to MFP."}

    if not 800 <= calories <= 8000:
        return not_sent("calories must be between 800 and 8000")
    if not all(0 <= g <= 1000 for g in (protein, carbs, fat)):
        return not_sent("protein, carbs and fat must be between 0 and 1000 g")
    macro_kcal = 4 * protein + 4 * carbs + 9 * fat
    if macro_kcal > calories + MAX_MACRO_EXCESS_KCAL:
        return not_sent(f"the macros add up to {macro_kcal:.0f} kcal, more than {calories:.0f}")
    day = datetime.date.today()
    try:
        current = await _read_item(day)
    except Exception as exc:  # noqa: BLE001 - nothing went out yet
        return not_sent(f"reading the current goal failed ({type(exc).__name__})")
    if current is None:
        return not_sent("MFP returned no current goal to update")

    write, error = await asyncio.to_thread(_post_once, _payload(current, day, calories, protein, carbs, fat))
    try:
        await asyncio.to_thread(mfp_client.persist_cached_session)
    except Exception:  # noqa: BLE001 - saving rotated cookies is retried by the next call
        pass
    try:
        stored = _summary(await _read_item(day))
    except Exception as exc:  # noqa: BLE001
        stored = None
        error = "; ".join(filter(None, [error, f"reading the goal back failed ({type(exc).__name__})"]))
    matches = None if stored is None else all(
        stored[k] is not None and abs(stored[k] - requested[k]) <= 1 for k in requested
    )
    return {"ok": write == "sent" and bool(matches), "write": write, "requested": requested,
            "stored": stored, "matches": matches, "error": error,
            "note": "Never call fitness_set_goal again to retry; check MFP instead."}
