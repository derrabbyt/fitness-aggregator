"""Phase review (coach-reviews ticket 03; spec, "Phase review").

- Schedule: every `reviews.phase_review_every_weeks` (10) weeks from the
  phase start: the job `phase-review` reviews phase weeks 1..10n on any tick
  from the day after week 10n (key "<phase id>:week-<10n>"; only the latest
  due one, no backlog). A phase end always gets one (key "<phase id>:end",
  the phase's whole span): confirming the end card runs it right away
  (`review_end`, on `phase_end.after_end`); the job catches up on a phase
  that ended within `END_CATCH_UP` without one (a crash, or a new phase
  start that ended it).
- Facts (code, `phase_summary.schema.json`): weight against the band (the
  weekly check-ins' `vs_band` counts) and the time goal, the strength trend
  (block_review's lift summary over the phase), targets and the
  maintenance estimate (start vs now), waist and body-fat estimates (the
  photo reviews'; the user's win), photo counts, and the calibration drift.
  With photo sets in the phase, the model also gets the phase start set
  (the first in the phase) and the latest set as images
  (`measurements.photos_compared`; one set alone goes as the start set).
- Calibration drift (`calibration`): per usable phase week (fully logged,
  enough weigh-ins, no unusable or glycogen-window day: the maintenance
  estimate's rules) the trend-implied expenditure = intake - weekly weight
  change x kcal_per_kg / 7. Code regresses it on the week's raw Strava /
  run kcal per day and wrestling sessions per day (lifting and other
  counted activity taken off first): the slopes are the implied run
  discount and kcal per wrestling session. A variable is judged only with
  `min_weeks` usable weeks and enough spread between weeks; it has drifted
  when the implied value is plausible and at least the drift threshold from
  the current one (`reviews.calibration`, assumptions). A drifted value
  becomes a calibration proposal (source `phase_review`) through
  proposals.propose, its card sent after the review; only while the phase
  is active (an ended phase's values go to the next phase's setup, in words).
- Text: the phase-review skill (COACH_DECISION_MODEL, no tools) writes it;
  after a phase end with no new phase active it asks what comes next.
  Without a usable answer code sends its own short summary, so every review
  goes out exactly once (`reviews.send`).
"""

import datetime
import json
import statistics
from typing import TYPE_CHECKING, Any

from .. import body_fat, history, phases, proposals, reviews, weekly_facts
from ..ports import Image
from ..registry import registry
from . import block_review, measurements, phase_end, photo_review, training_plan
from .proposals import send_card

if TYPE_CHECKING:
    from ..core import Coach

Date = datetime.date
DAY = datetime.timedelta(days=1)
SKILL = "phase-review"
KIND = "phase"
SOURCE = "phase_review"
SCHEDULED, PHASE_END = "scheduled", "phase_end"
END_CATCH_UP = datetime.timedelta(days=2)  # assumption: a missed end review is sent this long after the end
CALIBRATED = ("run_kcal_discount", "wrestling_kcal_per_session")


# --- triggers -----------------------------------------------------------------------


@registry.job("phase-review", order=61)
async def phase_review_job(coach: "Coach", now: datetime.datetime) -> None:
    since = (now - END_CATCH_UP).isoformat(timespec="seconds")
    for row in coach.db.all("SELECT id FROM phases WHERE status = 'ended' AND ended_at >= ? ORDER BY ended_at",
                            (since,)):
        phase = phases.get(coach, row["id"])
        if phase is not None:
            await review_end(coach, phase, now)
    phase = phases.active(coach)
    if phase is None:
        return
    every = phases.params_on(coach, now.date())["reviews"]["phase_review_every_weeks"]
    start = Date.fromisoformat(phase["start_date"])
    weeks = (now.date() - start).days // 7 // every * every
    if weeks < 1:
        return
    await _review(coach, phase, SCHEDULED, f"week-{weeks}", start + (weeks * 7 - 1) * DAY, now)


async def review_end(coach: "Coach", phase: dict[str, Any], now: datetime.datetime) -> None:
    """The review of a phase that just ended (`phase` as stored, with its end_date)."""
    if phase["end_date"] is None or phase["end_date"] < phase["start_date"]:
        return
    await _review(coach, phase, PHASE_END, "end", Date.fromisoformat(phase["end_date"]), now)


phase_end.after_end.append(review_end)


async def _review(coach: "Coach", phase: dict[str, Any], reason: str, key: str, end: Date,
                  now: datetime.datetime) -> None:
    key = f"{phase['id']}:{key}"
    if reviews.sent(coach, KIND, key):
        return
    data = facts(coach, phase, reason, end)
    made = _propose(coach, phase, data, now) if reason == SCHEDULED else []
    text = (await reviews.model_text(coach, SKILL, data, "phase_summary", now, phase=phase["phase_id"],
                                     images=_images(coach, data["measurements"]["photos_compared"]))
            or fallback_text(coach, phase, data))
    review_id = reviews.send(coach, kind=KIND, key=key, phase_row_id=phase["id"],
                             period_start=phase["start_date"], period_end=end.isoformat(), facts=data, text=text,
                             now=now)
    if review_id is None:
        return
    for result in made:
        send_card(coach, result)


# --- calibration proposals ----------------------------------------------------------


def _propose(coach: "Coach", phase: dict[str, Any], data: dict[str, Any],
             now: datetime.datetime) -> list[dict[str, Any]]:
    """A calibration proposal per drifted value; returns the new open ones (their cards go out after the review)."""
    active = phases.active(coach)
    if active is None or active["id"] != phase["id"]:
        return []
    made = []
    for key in CALIBRATED:
        item = data["calibration"][key]
        if not item["drifted"]:
            continue
        result = proposals.propose(coach, {
            "type": "calibration_change", "new_values": {key: item["suggested"]}, "source": SOURCE,
            "reason": f"Phase review: {item['evidence']}"}, now)
        item["proposal"] = {"id": result["id"], "status": result["status"]}
        if result["status"] == "open" and not result.get("referenced"):
            made.append(result)
    return made


# --- text ---------------------------------------------------------------------------


def _images(coach: "Coach", compared: dict[str, Any] | None) -> list[Image]:
    """The phase start set and the latest set as images (`photos_compared`), as the photo review sends them."""
    if compared is None:
        return []
    by_date = {s["date"]: s for s in measurements.photo_sets(coach)}
    out = photo_review.images(coach, "Phase start set", by_date[compared["start_set"]])
    if compared["latest_set"] is not None:
        out += photo_review.images(coach, "Latest set", by_date[compared["latest_set"]])
    return out


def fallback_text(coach: "Coach", phase: dict[str, Any], data: dict[str, Any]) -> str:
    name = coach.skills.params(phase["phase_id"]).get("name") or phase["phase_id"]
    w, t = data["weight"], data["targets"]
    lines = [f"Phase review: {name} ({_day(data['start_date'])} - {_day(data['end_date'])}, "
             f"{data['weeks_elapsed']} weeks)"]
    if w["change_kg"] is not None:
        lines.append(f"Weight trend: {w['start_trend_kg']:g} -> {w['current_trend_kg']:g} kg "
                     f"({w['change_kg']:+.1f} kg).")
    weeks = w["weeks"]
    lines.append(f"Weeks in the band: {weeks['in_band']}, below: {weeks['below_band'] + weeks['below_limit']}, "
                 f"above: {weeks['above_band'] + weeks['above_limit']}.")
    if t["start_avg_daily_kcal"] is not None and t["current_avg_daily_kcal"] is not None:
        lines.append(f"Daily target: {t['start_avg_daily_kcal']:,} -> {t['current_avg_daily_kcal']:,} kcal.")
    trend = data["training"]["strength_trend"]
    if trend["change_pct"] is not None:
        lines.append(f"Strength: {trend['change_pct']:+.1f} % over the phase ({trend['direction']}).")
    for key, label in (("run_kcal_discount", "Run discount"), ("wrestling_kcal_per_session", "Wrestling kcal")):
        item = data["calibration"][key]
        if item["drifted"]:
            lines.append(f"{label}: {item['evidence']}")
    if data["ask_what_next"]:
        lines.append("What comes next: a cut, maintenance or another bulk?")
    return "\n".join(lines)


def _day(iso: str) -> str:
    d = Date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')}"


# --- facts --------------------------------------------------------------------------


def facts(coach: "Coach", phase: dict[str, Any], reason: str, end: Date) -> dict[str, Any]:
    """The phase's facts over its start..`end` (`phase_summary.schema.json`)."""
    start = Date.fromisoformat(phase["start_date"])
    p = phases.params_for(coach.skills, phase["phase_id"], phases.setup_on(coach, phase, end))
    week = phases.phase_week(phase, end)
    lifts, training = block_review.lifts_over(coach, start, end)
    earlier = reviews.count(coach, phase["id"], KIND)
    time_goal = p.get("time_goal_weeks")
    setup = phase["setup"]
    return {
        "schema_version": 1,
        "phase_id": phase["phase_id"],
        "reason": reason,
        "is_first_review_of_phase": earlier == 0,
        "ask_what_next": reason == PHASE_END and phases.active(coach) is None,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "weeks_elapsed": week,
        "time_goal": {"weeks": time_goal, "weeks_left": time_goal - week if time_goal else None,
                      "goal": setup.get("goal"), "end_date": setup.get("end_date")},
        "weight": _weight(coach, phase, start, end, p, week),
        "targets": _targets(coach, phase, start, end),
        "maintenance_estimate": {"at_start_kcal": setup.get("maintenance_estimate_kcal"),
                                 **weekly_facts.maintenance_base(coach, end, p)},
        "lifts": lifts,
        "training": training,
        "measurements": _measurements(coach, phase, start, end, p),
        "calibration": calibration(coach, phase, start, end),
        "params": {"phase_review_every_weeks": p["reviews"]["phase_review_every_weeks"],
                   "calibration": p["reviews"]["calibration"]},
    }


def _weight(coach, phase, start: Date, end: Date, p, week: int) -> dict[str, Any]:
    first = phases.trend_weight(coach, start - DAY) or phase["setup"].get("starting_trend_weight_kg")
    current = phases.trend_weight(coach, end)
    change = round(current - first, 2) if current is not None and first is not None else None
    counts = dict.fromkeys(("in_band", "below_band", "above_band", "below_limit", "above_limit", "not_evaluated"), 0)
    seen: set[str] = set()
    for row in coach.db.all("SELECT iso_week, facts FROM weekly_checkins WHERE status = 'ok' AND phase_row_id = ?"
                            " AND end_date <= ? ORDER BY end_date DESC, id DESC", (phase["id"], end.isoformat())):
        if row["iso_week"] in seen or not row["facts"]:
            continue
        seen.add(row["iso_week"])
        counts[json.loads(row["facts"])["weight"]["vs_band"]] += 1
    return {"start_trend_kg": first, "current_trend_kg": current, "change_kg": change,
            "avg_rate_kg_per_week": round(change / ((end - start).days + 1) * 7, 2) if change is not None else None,
            "band": weekly_facts.weight_band(p, week), "weeks": counts}


def _targets(coach, phase, start: Date, end: Date) -> dict[str, Any]:
    first, last = phases.targets(coach, start), phases.targets(coach, end)
    rows = coach.db.all("SELECT valid_from, source, ref, surplus_kcal, avg_daily_target_kcal FROM targets"
                        " WHERE phase_row_id = ? AND valid_from <= ? ORDER BY id", (phase["id"], end.isoformat()))
    changes = [{"applied_on": r["valid_from"], "source": r["source"], "proposal_id": r["ref"],
                "avg_daily_target_kcal": round(r["avg_daily_target_kcal"]),
                "surplus_change_kcal": round(r["surplus_kcal"] - before["surplus_kcal"])}
               for before, r in zip(rows, rows[1:], strict=False)]

    def kcal(row, key):
        return round(row[key]) if row else None

    return {"start_avg_daily_kcal": kcal(first, "avg_daily_target_kcal"),
            "current_avg_daily_kcal": kcal(last, "avg_daily_target_kcal"),
            "start_base_maintenance_kcal": kcal(first, "base_maintenance_kcal"),
            "current_base_maintenance_kcal": kcal(last, "base_maintenance_kcal"),
            "start_surplus_kcal": kcal(first, "surplus_kcal"), "current_surplus_kcal": kcal(last, "surplus_kcal"),
            "changes": changes}


def _measurements(coach, phase, start: Date, end: Date, p) -> dict[str, Any]:
    span = (start.isoformat(), end.isoformat())
    waist = [{"date": w["date"], "cm": w["cm"]} for w in reversed(measurements.waist_history(coach, end))
             if span[0] <= w["date"] <= span[1]]
    estimates = [{"date": e["date"], "pct": e["pct"], "source": e["source"]}
                 for e in reversed(body_fat.estimates(coach)) if span[0] <= e["date"] <= span[1]]
    sets = [s for s in measurements.photo_sets(coach) if span[0] <= s["date"] <= span[1]]
    photo_reviews = reviews.count(coach, phase["id"], photo_review.KIND)
    compared = None
    if sets:
        latest = sets[-1]["date"] if len(sets) > 1 else None
        compared = {"start_set": sets[0]["date"], "latest_set": latest}
    return {"waist_cm_start": phase["setup"].get("waist_cm_start"), "waist": waist, "body_fat_estimates": estimates,
            "photos_enabled": bool(p["measurements"]["photos_enabled"]), "photo_sets": len(sets),
            "photo_reviews": photo_reviews, "photos_compared": compared}


# --- calibration drift --------------------------------------------------------------


def calibration(coach: "Coach", phase: dict[str, Any], start: Date, end: Date) -> dict[str, Any]:
    """The implied run discount and wrestling kcal over the phase's usable weeks, against the current values."""
    p_end = phases.params_on(coach, end)
    cp = p_end["reviews"]["calibration"]
    weeks = _usable_weeks(coach, start, end)
    run_x = [w["run_kcal_per_day"] for w in weeks]
    wrestling_x = [w["wrestling_per_day"] for w in weeks]
    enough = len(weeks) >= cp["min_weeks"]
    judged = {
        "run_kcal_discount": enough and _spread(run_x) >= cp["run_min_spread_kcal_per_day"],
        "wrestling_kcal_per_session":
            enough and _spread(wrestling_x) * 7 >= cp["wrestling_min_spread_sessions_per_week"],
    }
    columns = {"run_kcal_discount": run_x, "wrestling_kcal_per_session": wrestling_x}
    used = [k for k in CALIBRATED if judged[k]]
    slopes = _regress([w["implied_kcal"] for w in weeks], [columns[k] for k in used]) if used else None
    out: dict[str, Any] = {"weeks_used": len(weeks)}
    for key in CALIBRATED:
        current = p_end["activity"][key]
        implied = slopes[used.index(key)] if slopes is not None and key in used else None
        out[key] = _item(key, current, implied, judged[key] and implied is not None, len(weeks), cp)
    return out


def _item(key: str, current: float, implied: float | None, judged: bool, weeks: int,
          cp: dict[str, Any]) -> dict[str, Any]:
    if key == "run_kcal_discount":
        low, high = cp["run_discount_plausible"]
        threshold, step = cp["run_discount_drift"], 0.05
        what, varying = "a run discount of {}", "runs"
    else:
        low, high = cp["wrestling_plausible_kcal"]
        threshold, step = cp["wrestling_drift_kcal"], 25
        what, varying = "about {} kcal per wrestling session", "wrestling sessions"
    rounded = None if implied is None else round(round(implied / step) * step, 2)
    if key == "wrestling_kcal_per_session" and rounded is not None:
        rounded = round(rounded)
    plausible = rounded is not None and low <= rounded <= high
    drifted = judged and plausible and abs(rounded - current) >= threshold
    if not judged:
        evidence = (f"not judged: needs {cp['min_weeks']} usable weeks with {varying} varying between them "
                    f"({weeks} usable)")
    elif not plausible:
        evidence = f"the weeks imply {rounded:g}, outside {low:g}-{high:g}: too noisy to use, left as it is"
    else:
        evidence = (f"the weight trend over {weeks} usable weeks implies {what.format(f'{rounded:g}')} "
                    f"(set: {current:g})")
    return {"current": current, "implied": rounded if judged else None, "suggested": rounded if drifted else None,
            "judged": judged, "drifted": drifted, "evidence": evidence, "proposal": None}


def _usable_weeks(coach: "Coach", start: Date, end: Date) -> list[dict[str, Any]]:
    """Per usable phase week: the trend-implied expenditure minus lifting and other counted activity
    (kcal a day), raw run kcal a day and wrestling sessions a day."""
    out = []
    week_start = start
    while week_start + 6 * DAY <= end:
        week_end = week_start + 6 * DAY
        p = phases.params_on(coach, week_end)
        dates = [(week_start + n * DAY).isoformat() for n in range(7)]
        days = {d["date"]: d for d in history.days(coach.db, dates[0], dates[-1])}
        weights = history.weigh_ins(coach.db, dates[0], dates[-1])
        blocked = phases.unusable_days(coach, week_start, week_end, p)
        rate = weekly_facts.weekly_rate(coach, week_end)
        usable = (all(d in days and days[d]["logged"] and days[d]["kcal"] is not None for d in dates)
                  and len(weights) >= p["data"]["min_weighins_per_week"]
                  and not blocked.intersection(dates) and rate is not None)
        if usable:
            run = wrestling = other = 0.0
            for n in range(7):
                day = week_start + n * DAY
                activity = phases.params_on(coach, day)["activity"]
                counted = training_plan.counted_activity_on(coach, day, activity, planned_from=start)
                for s in counted["sessions"]:
                    if s["status"] == "skipped":
                        continue
                    if s["type"] == "run":
                        run += s["kcal_counted"] / activity["run_kcal_discount"]
                    elif s["type"] == "wrestling":
                        wrestling += 1
                    else:
                        other += s["kcal_counted"]
            intake = statistics.fmean(days[d]["kcal"] for d in dates)
            implied = intake - rate * p["maintenance_estimate"]["kcal_per_kg"] / 7
            out.append({"start_date": dates[0], "implied_kcal": implied - other / 7,
                        "run_kcal_per_day": run / 7, "wrestling_per_day": wrestling / 7})
        week_start += 7 * DAY
    return out


def _spread(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _regress(y: list[float], columns: list[list[float]]) -> list[float] | None:
    """Least-squares slopes of y on the columns, with an intercept; None when singular."""
    rows = [[1.0, *(c[i] for c in columns)] for i in range(len(y))]
    k = len(rows[0])
    # normal equations (X'X) b = X'y, solved by Gaussian elimination
    a = [[sum(r[i] * r[j] for r in rows) for j in range(k)] + [sum(r[i] * v for r, v in zip(rows, y, strict=True))]
         for i in range(k)]
    for col in range(k):
        pivot = max(range(col, k), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-9:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(k):
            if r != col:
                f = a[r][col] / a[col][col]
                a[r] = [x - f * z for x, z in zip(a[r], a[col], strict=True)]
    return [a[i][k] / a[i][i] for i in range(1, k)]
