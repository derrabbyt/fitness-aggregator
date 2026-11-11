"""The web page's Week (coach-web ticket 06): the `week` view, the check-in
week (the 7 days the weekly check-in judges), named by the ISO week of its
last day as the check-in names it.

- A judged week comes from the stored check-in (`weekly_checkin.stored`):
  the decision in plain words (hold, or the change and why), why a skipped
  week didn't count (one line by code), and the report as sent.
- The week holding today is in progress: what is known so far, no decision.
- Proposals (`proposals.py`) are shown read-only: those based on the week,
  plus every open one on the week in progress (where Home's banner leads).
  Approving, rejecting and countering stay in Telegram; there is no web
  command for them.

Number blocks (weight, intake, training, notes and flags) are parts of
`week` in their own modules: `@registry.view_part("week", "<key>",
schema="web_week_<key>", ...)`. `resolve(coach, query, now)` gives them the
week (dates, state, stored check-in).
"""

import dataclasses
import datetime
import json
import re
from typing import Any

from .. import history, phases, proposals, views, weekly_facts
from ..registry import registry
from . import weekly_checkin
from .web_home import check_in_week_start

Date = datetime.date
DAY = datetime.timedelta(days=1)
ISO_WEEK = re.compile(r"^(\d{4})-W(\d{2})$")

UNUSABLE_WORDS = {
    "stale_sync": "the data wasn't synced in time",
    "illness": "illness",
    "travel": "travel",
    "other_context": "a context note",
}


@dataclasses.dataclass(frozen=True)
class Week:
    iso_week: str
    start: Date
    end: Date
    today: Date
    stored: dict[str, Any] | None  # weekly_checkin.stored()

    @property
    def is_current(self) -> bool:
        return self.start <= self.today <= self.end


def resolve(coach, query: dict[str, str], now: datetime.datetime) -> Week:
    """The check-in week of `?week=YYYY-Www` (default: the one holding today).
    A week that hasn't started is refused."""
    today = now.date()
    raw = query.get("week")
    if not raw:
        start = check_in_week_start(coach, today)
    else:
        match = ISO_WEEK.match(raw)
        try:
            if match is None:
                raise ValueError
            # A check-in week ends the day before the check-in weekday and is named by that day's ISO week.
            weekday = weekly_facts.checkin_weekday(coach)
            end_weekday = ((0 if weekday is None else weekday) - 1) % 7
            start = Date.fromisocalendar(int(match[1]), int(match[2]), end_weekday + 1) - 6 * DAY
        except ValueError:
            raise views.WebError(400, f"{raw!r} is not a week (YYYY-Www).") from None
        if start > today:
            raise views.WebError(400, "That week hasn't started yet.")
    iso = weekly_facts.iso_week(start + 6 * DAY)
    stored = weekly_checkin.stored(coach, iso)
    if stored is not None:
        start = Date.fromisoformat(stored["start_date"])
    return Week(iso, start, start + 6 * DAY, today, stored)


@registry.view("week", schema="web_week")
def week_view(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    w = resolve(coach, query, now)
    phase = _phase_during(coach, w)
    state = _state(coach, w, phase)
    first = _first_phase_start(coach)
    prev_end = w.end - 7 * DAY
    return {
        "iso_week": w.iso_week,
        "start": w.start.isoformat(),
        "end": w.end.isoformat(),
        "is_current": w.is_current,
        "state": state,
        "phase_week": phases.phase_week(phase, w.end) if phase else None,
        "prev_week": weekly_facts.iso_week(prev_end) if first is not None and prev_end >= first else None,
        "next_week": None if w.is_current else weekly_facts.iso_week(w.end + 7 * DAY),
        "checkin_at": _checkin_at(coach, w, now),
        "note": _note(coach, w, state, phase, now),
        "decision": _decision(coach, w) if state == "decided" else None,
        "so_far": _so_far(coach, w) if state == "in_progress" else None,
        "proposals": _proposals(coach, w, now),
        "report": w.stored["report"] if w.stored else None,
        "freshness": views.freshness(coach, now),
    }


# --- state ---------------------------------------------------------------------------------


def _phase_during(coach, w: Week) -> dict[str, Any] | None:
    """The phase whose span covers the week's last day (the active one, or an ended one)."""
    for row in coach.db.all("SELECT * FROM phases WHERE start_date <= ? ORDER BY start_date DESC", (w.end.isoformat(),)):
        if row["ended_at"] is None or row["ended_at"][:10] >= w.start.isoformat():
            return {"id": row["id"], "phase_id": row["phase_id"], "start_date": row["start_date"]}
    return None


def _first_phase_start(coach) -> Date | None:
    value = coach.db.value("SELECT MIN(start_date) FROM phases")
    return Date.fromisoformat(value) if value else None


def _state(coach, w: Week, phase) -> str:
    if w.stored is not None:
        return "decided"
    if w.is_current:
        return "in_progress"
    if phase is None or w.start < Date.fromisoformat(phase["start_date"]):
        return "none"
    failed = coach.db.value("SELECT COUNT(*) FROM weekly_checkins WHERE status = 'failed' AND iso_week = ?",
                            (w.iso_week,))
    return "failed" if failed else "awaiting"


def _checkin_at(coach, w: Week, now: datetime.datetime) -> str | None:
    if w.stored is not None:
        return w.stored["created_at"]
    setting = phases.params(coach)["messaging"].get("weekly_checkin")
    if not setting:
        return None
    hour, minute = (int(x) for x in setting.strip().split(" ")[1].split(":"))
    moment = datetime.datetime.combine(w.end + DAY, datetime.time(hour, minute), tzinfo=now.tzinfo)
    return moment.isoformat(timespec="seconds")


def _note(coach, w: Week, state: str, phase, now: datetime.datetime) -> str | None:
    if state == "failed":
        return "The check-in for this week failed, so nothing changed. Send /checkin in Telegram to run it again."
    if state == "awaiting":
        at = _checkin_at(coach, w, now)
        if at is None:
            return "This week hasn't been judged: no check-in time is set."
        moment = datetime.datetime.fromisoformat(at)
        if moment > now:
            return f"The check-in judges this week on {moment.strftime('%a %d %b')} at {moment.strftime('%H:%M')}."
        return "This week hasn't been judged yet."
    if state == "none":
        if phase is None:
            return "No phase was active, so the coach didn't judge this week."
        return "The phase started during this week, so the coach didn't judge it."
    return None


def _so_far(coach, w: Week) -> dict[str, Any]:
    last = min(w.today, w.end)
    weigh_ins = history.weigh_ins(coach.db, w.start.isoformat(), last.isoformat())
    days = history.days(coach.db, w.start.isoformat(), last.isoformat())
    return {"days": (last - w.start).days + 1, "weigh_ins": len(weigh_ins),
            "food_days_logged": sum(1 for d in days if d["logged"] and d["kcal"] is not None)}


# --- decision ------------------------------------------------------------------------------


def _decision(coach, w: Week) -> dict[str, Any]:
    stored = w.stored
    verdict, facts = stored["verdict"], stored["facts"]
    mine = _decided_proposal(coach, w)
    change = mine is not None and mine["status"] != "blocked_by_guardrail"
    confirmation = verdict["confirmation"]
    return {
        "outcome": "change" if change else "hold",
        "change_kcal": round(mine["delta_kcal"]) if change else None,
        "direction": verdict["direction"],
        "why": verdict["reasoning"],
        "counts": stored["counts_for_confirmation"],
        "skip": _skip(stored["skip_reason"], verdict, facts),
        "confirmation": {"weeks": confirmation["consecutive_usable_weeks_same_direction"],
                         "required": confirmation["required_weeks"], "met": confirmation["met"]},
        "decided_at": stored["created_at"],
    }


def _decided_proposal(coach, w: Week) -> dict[str, Any] | None:
    """The calorie change the week's verdict asked for, as stored by propose_change
    (an identical open one from an earlier week is reused there)."""
    offer = w.stored["verdict"].get("proposal")
    if offer is None:
        return None
    rows = coach.db.all("SELECT id FROM proposals WHERE based_on_week = ? AND source = 'weekly_decision'"
                        " AND type = 'calorie_change' ORDER BY created_at DESC, rowid DESC", (w.iso_week,))
    for row in rows:
        return proposals.get(coach, row["id"])
    for p in proposals.open_proposals(coach):
        if p["type"] == "calorie_change" and round(p["delta_kcal"]) == round(offer["delta_kcal"]):
            return p
    return None


def _skip(reason: str | None, verdict: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any] | None:
    """Why a skipped week didn't count, in one line."""
    if reason is None:
        return None
    p, dq = facts["params"], facts["data_quality"]
    if reason == "unusable":
        found = list(dict.fromkeys([*dq["code_unusable_reasons"], *verdict["unusable_reasons"]]))
        parts = []
        for r in found:
            if r == "too_few_weigh_ins":
                parts.append(f"{dq['weigh_in_count']} weigh-ins ({p['data']['min_weighins_per_week']} needed)")
            elif r == "incomplete_food_log":
                parts.append(f"food logged on {dq['food_days_logged']} of 7 days")
            else:
                parts.append(UNUSABLE_WORDS.get(r, r.replace("_", " ")))
        text = "This week didn't count: " + ("; ".join(parts) if parts else "the data wasn't good enough") + "."
    elif reason == "glycogen_window":
        text = (f"Phase week {facts['week']['phase_week']} isn't judged: early weight change is mostly water "
                "and glycogen.")
    elif reason == "adherence_gate":
        intake = facts["intake"]
        if not dq["food_log_complete"]:
            why = f"food logged on {dq['food_days_logged']} of 7 days"
        elif intake["deviation_pct"] is not None:
            side = "over" if intake["deviation_pct"] > 0 else "under"
            why = (f"intake was {abs(intake['deviation_pct']):.1f} % {side} target "
                   f"(within ±{p['adherence']['weekly_intake_tolerance_pct']:g} % counts)")
        else:
            why = "intake was off target"
        text = f"This week didn't count: {why}."
    else:  # sport_load
        text = "A heavy sport week: it doesn't count and gives no calorie increase."
    return {"reason": reason, "text": text}


# --- proposals -----------------------------------------------------------------------------


def _proposals(coach, w: Week, now: datetime.datetime) -> list[dict[str, Any]]:
    rows = coach.db.all("SELECT id FROM proposals WHERE based_on_week = ? ORDER BY created_at, rowid", (w.iso_week,))
    found = [proposals.get(coach, r["id"]) for r in rows]
    if w.is_current:
        found += [p for p in proposals.open_proposals(coach) if p["id"] not in {f["id"] for f in found}]
    found.sort(key=lambda p: p["created_at"])
    return [_proposal(coach, p, now) for p in found]


def _proposal(coach, p: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    outcome_raw = coach.db.value("SELECT outcome FROM proposals WHERE id = ?", (p["id"],))
    outcome = json.loads(outcome_raw) if outcome_raw else None
    target = None
    goal_after = None
    if p["status"] == "open":
        goal_after = proposals.mfp_goal_after(coach, p, now.date())
        current = phases.targets(coach, now.date())
        if p["type"] == "calorie_change" and current is not None:
            before = round(current["avg_daily_target_kcal"])
            target = {"before": before, "after": before + round(p["delta_kcal"])}
    elif outcome is not None and "avg_daily_target_before_kcal" in outcome:
        target = {"before": outcome["avg_daily_target_before_kcal"], "after": outcome["avg_daily_target_after_kcal"]}
    return {
        "id": p["id"],
        "type": p["type"],
        "source": p["source"],
        "status": p["status"],
        "based_on_week": p["based_on_week"],
        "change": proposals.describe_change(p),
        "delta_kcal": round(p["delta_kcal"]) if p["delta_kcal"] is not None else None,
        "new_values": p["new_values"],
        "reason": p["reason"],
        "agent_disagrees": p["agent_disagrees"],
        "user_reason": p["user_reason"],
        "created_at": p["created_at"],
        "decided_at": p["decided_at"],
        "guardrail": {"passed": p["guardrail"]["passed"], "details": p["guardrail"]["details"]},
        "applied_on": outcome["applied_on"] if outcome else None,
        "mfp_goal_after_kcal": goal_after,
        "avg_daily_target_kcal": target,
    }
