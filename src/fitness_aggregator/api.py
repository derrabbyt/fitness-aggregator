"""FastAPI backend: a day's MFP nutrition, steps and workouts plus Hevy workouts.

    uv run fa-api    # http://127.0.0.1:8000 (UI, /api/day?date=YYYY-MM-DD, /api/today)
                     # http://127.0.0.1:8001/{mfp,hevy}/mcp (tools for the bot)

This process owns the MFP session (state/mfp): the REST endpoints call
mfp-mcp's functions in-process and tools_server serves its MCP tools from the
same process. The host's stdio `mfp` server (.mcp.json) uses the same files, so
don't run it while this is up.
"""

import asyncio
import datetime
import logging
import os
import re
from typing import Any

from .mfp import mfp_env

os.environ.update(mfp_env())  # before mfp-mcp reads its config paths
os.environ.pop("MFP_COOKIE", None)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from myfitnesspal_mcp import server as mfp_server  # noqa: E402
from myfitnesspal_mcp.mfp_web import api_headers  # noqa: E402

from . import hevy  # noqa: E402
from .config import ROOT  # noqa: E402

logger = logging.getLogger(__name__)
WEB_DIST = ROOT / "web" / "dist" / "web" / "browser"

app = FastAPI(title="fitness-aggregator")


class _LogContext:
    """Stands in for the MCP request context that mfp-mcp reports progress to."""

    async def info(self, message: str) -> None:
        logger.info(message)


KM_PER_MILE = 1.609344


def _metric(name: str | None) -> str | None:
    """MFP's v2 API names exercises in imperial units, e.g.
    "Running (jogging), 5.2 mph (11.5 min mile)" -> "Running (jogging), 8.4 km/h (7:09 min/km)"."""
    if not name:
        return name

    def speed(m: re.Match) -> str:
        return f"{float(m.group(1)) * KM_PER_MILE:.1f} km/h"

    def pace(m: re.Match) -> str:
        seconds = round(float(m.group(1)) * 60 / KM_PER_MILE)
        return f"{seconds // 60}:{seconds % 60:02d} min/km"

    name = re.sub(r"(\d+(?:\.\d+)?) mph", speed, name)
    return re.sub(r"(\d+(?:\.\d+)?) min(?:ute)? mile", pace, name)


def _distance_km(distance: dict | None) -> float | None:
    """v2 exercise entries carry {"unit": "miles", "value": ...}; 0 means none recorded."""
    if not distance or not distance.get("value"):
        return None
    factor = {"miles": KM_PER_MILE, "kilometers": 1.0, "km": 1.0, "meters": 0.001}.get(distance.get("unit"))
    return round(distance["value"] * factor, 2) if factor else None


def _mfp_diary_items(day: datetime.date):
    def op(store, client):
        resp = client.session.get(
            f"{client.BASE_API_URL.rstrip('/')}/v2/diary",
            params={"entry_date": day.isoformat()},
            headers=api_headers(client, {"Accept": "application/json"}),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("items") or []

    return mfp_server.with_session(_LogContext(), op)


def _activity(items: list[dict]) -> tuple[int | None, list[dict[str, Any]]]:
    """Steps and exercise entries (metric) from /v2/diary items."""
    steps = next((i.get("steps") for i in items if i.get("type") == "steps_aggregate"), None)
    workouts = [
        {
            "name": _metric((i.get("exercise") or {}).get("description")),
            "source": i.get("source") or "manual",
            "minutes": round((i.get("duration") or 0) / 60),
            "distance_km": _distance_km(i.get("distance")),
            "kcal": (i.get("energy") or {}).get("value"),
            "start": i.get("start_time"),
        }
        for i in items
        if i.get("type") == "exercise_entry" and not i.get("is_calorie_adjustment")
    ]
    return steps, workouts


async def fitness_get_activity(date: str | None = None) -> dict[str, Any]:
    """Steps and MyFitnessPal exercise entries (e.g. synced Strava runs) for a
    day, in metric units: name, source, minutes, distance_km, kcal, start.
    date: YYYY-MM-DD (default: today). Hevy strength workouts: use hevy_* tools."""
    day = datetime.date.fromisoformat(date) if date else datetime.date.today()
    steps, workouts = _activity(await _mfp_diary_items(day))
    return {"date": day.isoformat(), "steps": steps, "workouts": workouts}


QUICK_ADD_MEALS = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "snacks": "Snacks"}


async def fitness_quick_add(
    calories: float,
    protein: float | None = None,
    carbs: float | None = None,
    fat: float | None = None,
    meal: str = "breakfast",
    date: str | None = None,
) -> dict[str, Any]:
    """Quick Add calories (and optional macros in grams) to the MyFitnessPal
    diary, like the website's "Quick add calories". Adds an entry every call:
    send once, never retry. meal: breakfast|lunch|dinner|snacks or a meal name.
    date: YYYY-MM-DD (default today)."""
    day = datetime.date.fromisoformat(date) if date else datetime.date.today()
    if not 0 < calories <= 50000:
        raise ValueError("calories must be between 0 and 50000")
    contents: dict[str, Any] = {"energy": {"value": round(calories, 1), "unit": "calories"}}
    for key, value in (("protein", protein), ("carbohydrates", carbs), ("fat", fat)):
        if value is not None:
            contents[key] = round(max(value, 0), 1)
    item = {
        "type": "quick_add",
        "date": day.isoformat(),
        "meal_name": QUICK_ADD_MEALS.get(meal.lower(), meal),
        "nutritional_contents": contents,
    }

    def op(store, client):
        # MFP's v2 API, the same call the website's Quick Add makes.
        resp = client.session.post(
            f"{client.BASE_API_URL.rstrip('/')}/v2/diary",
            json={"items": [item]},
            headers=api_headers(client, {"Accept": "application/json", "Content-Type": "application/json"}),
            timeout=30,
        )
        resp.raise_for_status()
        return [i.get("id") for i in resp.json().get("items") or []]

    ids = await mfp_server.with_session(_LogContext(), op)
    refresh = await mfp_server.refresh_after_write(_LogContext(), day)
    return {"ok": True, "quick_add": item, "ids": ids, **refresh}


async def _mfp_day(day: datetime.date) -> dict[str, Any]:
    summary = await mfp_server.fitness_get_day(date=day.isoformat(), ctx=_LogContext())
    items = await _mfp_diary_items(day)
    # Latest weigh-in, which may be from an earlier day. The account displays kg,
    # and MFP returns weights in the account's display unit.
    trend = await mfp_server.fitness_get_trends(
        metric="weight", start=(day - datetime.timedelta(days=90)).isoformat(), end=day.isoformat(), ctx=_LogContext()
    )
    points = trend.get("points") or []
    weight = {"kg": points[-1]["value"], "date": points[-1]["day"]} if points else None
    steps, workouts = _activity(items)
    n = summary["nutrition"]
    return {
        "nutrition": {k: n.get(k) for k in ("calories", "goal_calories", "protein", "carbs", "fat")},
        "steps": steps,
        "weight": weight,
        "workouts": workouts,
    }


HEVY_SCAN_LIMIT = 300  # workouts scanned back from the newest (pages of 5)


def _hevy_day(day: datetime.date) -> list[dict[str, Any]]:
    workouts = []
    with hevy.client() as c:
        username = c.users.get_account()["username"]
        for n, w in enumerate(c.workouts.iter_paged(username, page_size=hevy.PAGE_SIZE)):
            if n >= HEVY_SCAN_LIMIT:
                break
            start = datetime.datetime.fromtimestamp(w["start_time"])
            if start.date() < day:
                break  # newest first
            if start.date() > day:
                continue
            end = datetime.datetime.fromtimestamp(w["end_time"]) if w.get("end_time") else None
            workouts.append(
                {
                    "name": w.get("name"),
                    "start": start.isoformat(timespec="minutes"),
                    "minutes": round((end - start).total_seconds() / 60) if end else None,
                    "exercises": [
                        {
                            "title": e.get("title"),
                            "sets": [
                                {k: s.get(k) for k in ("weight_kg", "reps", "distance_meters", "duration_seconds") if s.get(k) is not None}
                                for s in e.get("sets") or []
                            ],
                        }
                        for e in w.get("exercises") or []
                    ],
                }
            )
    return workouts


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness only: never touches MFP or Hevy, so checks can't rotate sessions."""
    return {"status": "ok"}


@app.get("/api/today")
async def today() -> dict[str, Any]:
    return await day_summary(None)


@app.get("/api/day")
async def day_summary(date: datetime.date | None = None) -> dict[str, Any]:
    """One day (default today, local time): nutrition, steps, latest weight up to
    that day, MFP and Hevy workouts."""
    day = date or datetime.date.today()
    if day > datetime.date.today():
        raise HTTPException(400, "date is in the future")
    mfp_result, hevy_result = await asyncio.gather(
        _mfp_day(day), asyncio.to_thread(_hevy_day, day), return_exceptions=True
    )
    errors = {}
    if isinstance(mfp_result, BaseException):
        logger.exception("MFP failed", exc_info=mfp_result)
        errors["mfp"] = str(mfp_result)
        mfp_result = {"nutrition": None, "steps": None, "weight": None, "workouts": []}
    if isinstance(hevy_result, BaseException):
        logger.exception("Hevy failed", exc_info=hevy_result)
        errors["hevy"] = str(hevy_result)
        hevy_result = []
    return {
        "date": day.isoformat(),
        "nutrition": mfp_result["nutrition"],
        "steps": mfp_result["steps"],
        "weight": mfp_result["weight"],
        "mfp_workouts": mfp_result["workouts"],
        "hevy_workouts": hevy_result,
        "errors": errors,
    }


if WEB_DIST.is_dir():
    # Built Angular app; html=True serves index.html for "/".
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")


def main() -> None:
    import uvicorn

    from .tools_server import build_app

    logging.basicConfig(level=logging.INFO)
    web = uvicorn.Server(
        uvicorn.Config(app, host=os.environ.get("FA_HOST", "127.0.0.1"), port=int(os.environ.get("FA_PORT", "8000")))
    )
    tools = uvicorn.Server(
        uvicorn.Config(
            build_app(),
            host=os.environ.get("FA_TOOLS_HOST", "127.0.0.1"),
            port=int(os.environ.get("FA_TOOLS_PORT", "8001")),
        )
    )

    async def serve() -> None:
        # If either server stops, stop the process so Docker restarts both.
        done, pending = await asyncio.wait(
            [asyncio.create_task(web.serve()), asyncio.create_task(tools.serve())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        web.should_exit = tools.should_exit = True
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()

    asyncio.run(serve())
