"""Fakes for the Coach seam: api client, model client, clock and outbox.

Extend these as tickets need: the fake api grows methods that return canned
records and record writes, the fake model returns scripted replies.
"""

import datetime
from typing import Any

from fa_coach.ports import Edit, ModelReply, ModelRequest, Outgoing, Send

TZ = datetime.timezone(datetime.timedelta(hours=1))  # Europe/Vienna in winter


class FakeClock:
    def __init__(self, start: datetime.datetime = datetime.datetime(2026, 11, 9, 9, 0, tzinfo=TZ)):
        self.current = start

    def now(self) -> datetime.datetime:
        return self.current

    def advance(self, **delta: float) -> datetime.datetime:
        self.current += datetime.timedelta(**delta)
        return self.current


class FakeApi:
    """fa-api with canned history. Records every call as (name, args).

    `days` maps "YYYY-MM-DD" to the parts of that day's MFP record that differ
    from an empty day (see `mfp_day`); `sessions` holds Hevy sessions (see
    `session`). A method named in `fail` raises like an unreachable api."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.days: dict[str, dict[str, Any]] = {}
        self.sessions: list[dict[str, Any]] = []
        self.fail: set[str] = set()

    async def mfp_days(self, start: datetime.date, end: datetime.date) -> list[dict[str, Any]]:
        self._call("mfp_days", start=start, end=end)
        days = []
        day = start
        while day <= end:
            days.append(mfp_day(day.isoformat(), **self.days.get(day.isoformat(), {})))
            day += datetime.timedelta(days=1)
        return days

    async def hevy_sessions(self, start: datetime.date, end: datetime.date) -> list[dict[str, Any]]:
        self._call("hevy_sessions", start=start, end=end)
        found = [s for s in self.sessions if start.isoformat() <= s["date"] <= end.isoformat()]
        return sorted(found, key=lambda s: s["start"], reverse=True)  # newest first, like Hevy

    def _call(self, name: str, **args: Any) -> None:
        self.calls.append((name, args))
        if name in self.fail:
            raise RuntimeError("502 Bad Gateway")

    def ranges(self, name: str) -> list[tuple[str, str]]:
        return [(a["start"].isoformat(), a["end"].isoformat()) for n, a in self.calls if n == name]


def mfp_day(date: str, *, food: dict[str, Any] | None = None, weight_kg: float | None = None,
            steps: int | None = None, exercises: list[dict[str, Any]] | None = None,
            error: str | None = None) -> dict[str, Any]:
    """One day as `GET /api/sync/mfp` returns it."""
    empty = {"kcal": None, "protein_g": None, "carbs_g": None, "fat_g": None, "fiber_g": None,
             "produce_g": None, "complete": False, "entries": 0}
    return {"date": date, "food": {**empty, **(food or {})}, "weight_kg": weight_kg, "steps": steps,
            "exercises": exercises or [], "error": error}


def food(kcal: float, protein_g: float = 180, carbs_g: float = 250, fat_g: float = 70,
         fiber_g: float | None = 30, complete: bool = False, entries: int = 8) -> dict[str, Any]:
    return {"kcal": kcal, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g, "fiber_g": fiber_g,
            "produce_g": None, "complete": complete, "entries": entries}


def run(kcal: float, distance_km: float, minutes: float) -> dict[str, Any]:
    return {"name": "Running (jogging)", "source": "strava", "run": True, "kcal": kcal,
            "distance_km": distance_km, "minutes": minutes, "start": None}


def session(id: str, date: str, *exercises: dict[str, Any], hour: int = 6) -> dict[str, Any]:
    """One Hevy session as `GET /api/sync/hevy` returns it."""
    return {"id": id, "name": "Pull", "date": date, "start": f"{date}T{hour:02d}:30:00+01:00",
            "end": f"{date}T{hour + 1:02d}:30:00+01:00", "minutes": 60, "exercises": list(exercises)}


def exercise(title: str, *sets: tuple[float | None, int], exercise_id: str | None = None,
             exercise_type: str | None = "weight_reps") -> dict[str, Any]:
    """`sets` as (weight_kg, reps)."""
    return {"exercise_id": exercise_id or title.lower().replace(" ", "-"), "title": title,
            "exercise_type": exercise_type,
            "sets": [{"type": "normal", "weight_kg": w, "reps": r, "distance_m": None, "duration_s": None,
                      "rpe": None} for w, r in sets]}


class FakeModel:
    """Returns scripted replies in order and records every request it was given."""

    def __init__(self, *replies: ModelReply) -> None:
        self.replies = list(replies)
        self.requests: list[ModelRequest] = []

    async def run(self, request: ModelRequest) -> ModelReply:
        self.requests.append(request)
        if not self.replies:
            raise AssertionError(f"unexpected model call: {request.task_skill}")
        return self.replies.pop(0)


class FakeOutbox:
    def __init__(self) -> None:
        self.items: list[Outgoing] = []

    def put(self, item: Outgoing) -> None:
        self.items.append(item)

    @property
    def sent(self) -> list[Send]:
        return [i for i in self.items if isinstance(i, Send)]

    @property
    def texts(self) -> list[str]:
        return [i.text for i in self.sent]

    @property
    def edits(self) -> list[Edit]:
        return [i for i in self.items if isinstance(i, Edit)]

    def clear(self) -> None:
        self.items.clear()
