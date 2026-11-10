"""Lift progression in the coach (ticket 08); the numbers are in progression.py.

- Weekly facts: a facts hook fills `training` (progression.week).
- Every exercise logged in Hevy is recorded and classified by the model as
  `counts` or `excluded` (its judgement): at phase start (phase-start skill,
  which shows the list), when a new exercise first shows up in a synced
  session during a phase (the `new-exercises` job asks the new-exercise
  skill, which classifies it and tells the user; the message counts toward
  the daily limit and goes to the weekly report when the limit is reached),
  and in chat when the user flips one. Until classified, an exercise counts.
- Model tools: `classify_exercises`, `get_tracked_exercises`. Baseline resets
  and pauses are written through progression.mark_reset / set_paused
  (ticket 12's chat tools and buttons).
"""

import datetime
import logging
from typing import Any

from .. import messaging, phases, progression, weekly_facts
from ..ask import ToolError
from ..ports import ModelError
from ..registry import registry

logger = logging.getLogger("fa-coach")

Date = datetime.date
DAY = datetime.timedelta(days=1)
NEW_EXERCISE_SKILLS = ("new-exercise",)


def _training_facts(coach, facts: dict[str, Any], now: datetime.datetime) -> None:
    week = facts["week"]
    phase = phases.active(coach)
    facts["training"] = {
        **progression.week(coach, Date.fromisoformat(week["start_date"]), Date.fromisoformat(week["end_date"]),
                           Date.fromisoformat(phase["start_date"]) if phase else None),
        "missed_sessions": facts["training"]["missed_sessions"],
    }


weekly_facts.facts_hooks.append(_training_facts)


def history_start(today: Date) -> Date:
    return today - phases.HISTORY_WEEKS * 7 * DAY


# --- tools -------------------------------------------------------------------------


@registry.tool(
    "classify_exercises",
    "Classify exercises from the Hevy history, by your judgement or when the user flips one: `counts` (the default: "
    "compounds, machines, most bigger isolation work) decides weekly progression; `excluded` (prehab/rehab and slow "
    "movers such as lateral raises, tibialis raises, Copenhagen plank, hip flexor raises, abs, plyometrics like pogo "
    "hops and box jumps) is still logged and its PRs named, but has no effect on the A–E decision and gets no stall "
    "flags. Use exercise ids from get_tracked_exercises (or the setup's `exercises`).",
    {
        "type": "object",
        "properties": {
            "exercises": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "exercise_id": {"type": "string"},
                        "classification": {"enum": list(progression.CLASSES)},
                        "reason": {"type": "string", "description": "A few words, e.g. 'main compound', 'prehab'."},
                    },
                    "required": ["exercise_id", "classification"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["exercises"],
        "additionalProperties": False,
    },
)
async def classify_exercises(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    items = args["exercises"]
    titles = {}
    for item in items:
        known = progression.known_exercise(coach, item["exercise_id"])
        if known is None:
            raise ToolError(f"exercise_id {item['exercise_id']!r} is not in the synced Hevy history; "
                            "see get_tracked_exercises")
        titles[item["exercise_id"]] = known["title"]
    with coach.db.transaction():
        for item in items:
            progression.classify(coach, item["exercise_id"], item["classification"], item.get("reason"), now)
    return {"classified": [{"exercise_id": i["exercise_id"], "name": titles[i["exercise_id"]],
                            "classification": i["classification"]} for i in items]}


@registry.tool(
    "get_tracked_exercises",
    "Exercises in the synced Hevy history (last 16 weeks), most often done first: id, title, Hevy type, whether "
    "it's a bodyweight exercise, sessions, last date, classification (counts / excluded; null = not classified "
    "yet, counts), paused.",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def get_tracked_exercises(coach, args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    return {"exercises": progression.exercises(coach, history_start(now.date()), now.date())}


# --- new exercises -----------------------------------------------------------------


@registry.job("new-exercises", order=30)  # after a sync, before the weekly check-in
async def new_exercises(coach, now: datetime.datetime) -> None:
    phase = phases.active(coach)
    if phase is None:
        return
    today = now.date()
    new = [e for e in progression.unclassified(coach, Date.fromisoformat(phase["start_date"]), today)
           if coach.db.once(f"new-exercise:{e['exercise_id']}:{today.isoformat()}", now)]  # retried next day
    if not new:
        return
    known = [{k: e[k] for k in ("exercise_id", "title", "classification")}
             for e in progression.exercises(coach, history_start(today), today) if e["classification"] is not None]
    try:
        answer = await coach.ask(NEW_EXERCISE_SKILLS, {"new_exercises": new, "classified_exercises": known},
                                 tools=("classify_exercises",), now=now)
    except ModelError as exc:
        logger.warning("new exercise classification: model error %s", exc)
        return
    if not answer.text:
        return
    if not messaging.send(coach, answer.text, now, kind="new-exercise"):
        messaging.defer(coach, today, answer.text, "new-exercise", now)
