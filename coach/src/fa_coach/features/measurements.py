"""Waist and photo check-ins (spec, "Measurements"). Code only, no model call.

- Due dates come from the active phase's start date and the measurement
  params (`measurements.waist_every_weeks`, `photos_every_weeks`,
  `photos_enabled`, the last one a setup value the user can switch in chat
  through `record_setup_value`). Photos are due on the start date (the
  baseline set) and every `photos_every_weeks` after it; the waist was taken
  at the start (setup value `waist_cm_start`), so it is due every
  `waist_every_weeks` after the start.
- `measurements_due(coach, start, end)`: what is due in a date range (the
  weekly report's "due next week").
- Reminder job: the evening before a due date, from the user's evening
  reminder time (`messaging.evening_reminder_time`), one message asks for
  what is due tomorrow morning (photos with the protocol: morning, fasted,
  unpumped); sent once per due date, unless the value already came in. A
  missed evening (coach down, no evening time set, held back by the daily
  message limit) is reminded once from `REMINDER_TIME` on the due day, or
  later in the same period. The baseline photo set is due on the start date
  and reminded that day. Reminders count toward the daily message limit
  (`messaging.send`).
- Photos sent to the chat are stored under the coach's state directory as
  `photos/<date>/<n>.jpg`, one set per day, and acknowledged. Waist values
  ("waist 84.5", or a bare "84.5" while a waist reminder is open) are stored
  with their date. Read them with `photo_sets(coach)` and `waist_values(coach)`;
  `waist_history(coach, day)` adds each phase's start value (the chat's
  `waist_history` tool).
  Photos are kept whenever they arrive, even with photos off.
"""

import datetime
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import messaging, phases
from ..registry import registry

if TYPE_CHECKING:
    from ..core import Coach

Date = datetime.date
KINDS = ("waist", "photos")
REMINDER_TIME = datetime.time(7, 0)  # assumption: a missed evening reminder goes out the due morning, before breakfast

PHOTOS_DIR = "photos"
WAIST_CM = (40, 200)  # as the phase-setup schema's waist_cm_start
_NUMBER = r"(\d{2,3}(?:[.,]\d+)?)\s*(?:cm)?\s*[.!]*\s*$"
WAIST = re.compile(r"(?i)^\s*(?:my\s+)?waist(?:\s+is)?\s*[:=]?\s*" + _NUMBER)
BARE = re.compile(r"(?i)^\s*" + _NUMBER)
WAIST_WORD = re.compile(r"(?i)\bwaist\b")
NUMBERS = re.compile(r"\d+(?:[.,]\d+)?")

PHOTO_PROTOCOL = ("Same spot and same light, camera at hip height, in the morning, fasted and unpumped, "
                  "same poses as last time.")


def measurements_due(coach: "Coach", start: Date, end: Date) -> list[dict[str, str]]:
    """Waist and photo check-ins due from `start` to `end` (inclusive) in the
    active phase, by date: [{"date": "YYYY-MM-DD", "kind": "waist"|"photos"}].
    Photos only while photos are on. Empty without an active phase."""
    phase = phases.active(coach)
    if phase is None:
        return []
    m = phases.params(coach)["measurements"]
    phase_start = Date.fromisoformat(phase["start_date"])
    every = {"waist": m["waist_every_weeks"], "photos": m["photos_every_weeks"]}
    first = {"waist": 1, "photos": 0}  # the waist at the start is a setup value
    kinds = [k for k in KINDS if k != "photos" or m["photos_enabled"]]
    due = []
    day = max(start, phase_start)
    while day <= end:
        weeks, rest = divmod((day - phase_start).days, 7)
        for kind in kinds:
            if rest == 0 and weeks % every[kind] == 0 and weeks // every[kind] >= first[kind]:
                due.append({"date": day.isoformat(), "kind": kind})
        day += datetime.timedelta(days=1)
    return due


# --- reminders -------------------------------------------------------------------


@registry.job("measurement-reminders")
async def remind(coach: "Coach", now: datetime.datetime) -> None:
    phase = phases.active(coach)
    if phase is None:
        return
    today = now.date()
    p = phases.params(coach)
    # Tomorrow's check-in is announced from the evening reminder time. What is
    # due today or earlier (the baseline set, a missed evening, one held back
    # by the daily message limit) goes out from REMINDER_TIME, not right
    # after midnight.
    evening = p["messaging"].get("evening_reminder_time")
    if evening and now.time() >= datetime.time.fromisoformat(evening):
        horizon = today + datetime.timedelta(days=1)
    elif now.time() >= REMINDER_TIME:
        horizon = today
    else:
        return
    m = p["measurements"]
    longest = max(m["waist_every_weeks"], m["photos_every_weeks"]) * 7
    latest: dict[str, str] = {}
    for item in measurements_due(coach, today - datetime.timedelta(days=longest - 1), horizon):
        latest[item["kind"]] = item["date"]  # in date order: the last one wins
    open_ = [(kind, due) for kind, due in sorted(latest.items(), key=lambda kv: KINDS.index(kv[0]))
             if not received_since(coach, kind, due)
             and (due > today.isoformat() or now.time() >= REMINDER_TIME)]
    # Counts toward the daily message limit; at the limit nothing is claimed,
    # so the reminder goes out later (on the due day; still once).
    if not open_ or not messaging.can_send(coach, now):
        return
    asked = [(kind, due) for kind, due in open_
             if coach.db.once(f"measurement-reminder:{phase['id']}:{kind}:{due}", now)]
    if asked:
        messaging.send(coach, _reminder_text(asked, today), now, kind="measurement-reminder")


def received_since(coach: "Coach", kind: str, day: str) -> bool:
    table, column = ("waist_measurements", "date") if kind == "waist" else ("photos", "set_date")
    return coach.db.value(f"SELECT COUNT(*) FROM {table} WHERE {column} >= ?", (day,)) > 0


def _reminder_text(asked: list[tuple[str, str]], today: Date) -> str:
    tomorrow = {kind for kind, due in asked if due > today.isoformat()}
    kinds = [kind for kind, _ in asked]
    lines = ["📏 Check-in tomorrow morning." if len(tomorrow) == len(kinds) else "📏 Check-in day."]
    if "waist" in kinds:
        when = "Tomorrow morning, send" if "waist" in tomorrow else "Send"
        lines.append(f"{when} your waist measurement in cm, e.g. \"waist 84.5\".")
    if "photos" in kinds:
        when = "Tomorrow morning, take" if "photos" in tomorrow else "Send"
        lines.append(f"{when} your progress photo set{' and send it' if 'photos' in tomorrow else ''} here. "
                     f"Photo protocol: {PHOTO_PROTOCOL}")
    return "\n".join(lines)



# --- waist -----------------------------------------------------------------------


@registry.text(order=60)
async def waist_text(coach: "Coach", text: str, now: datetime.datetime) -> bool:
    cm = _waist_in(text, coach, now)
    if cm is None:
        return False
    problem = waist_problem(cm)
    if problem:
        coach.say(f"{problem}; send it in cm, e.g. \"waist 84.5\".")
        return True
    day = now.date()
    add_waist(coach, cm, day, now)
    coach.say(f"📏 Saved: waist {cm:g} cm on {day.isoformat()}.")
    return True


def waist_problem(cm: float) -> str | None:
    """Why `cm` isn't a plausible waist value, or None (chat and the web page)."""
    if not WAIST_CM[0] <= cm <= WAIST_CM[1]:
        return f"{cm:g} cm doesn't look like a waist measurement"
    return None


def add_waist(coach: "Coach", cm: float, day: Date, now: datetime.datetime) -> None:
    """Store a waist value for `day` (checked with `waist_problem` first)."""
    coach.db.execute("INSERT INTO waist_measurements (date, cm, created_at) VALUES (?, ?, ?)",
                     (day.isoformat(), cm, now.isoformat(timespec="seconds")))


def _waist_in(text: str, coach: "Coach", now: datetime.datetime) -> float | None:
    """The waist value in `text`: "waist 84.5 cm", a sentence with "waist" and
    one plausible number, or a bare number while a waist reminder is open.
    Questions and anything else go on to the chat."""
    if "?" in text:
        return None
    match = WAIST.match(text) or (BARE.match(text) if _waist_reminder_open(coach, now) else None)
    if match:
        return _float(match.group(1))
    numbers = [_float(n) for n in NUMBERS.findall(text)]
    if WAIST_WORD.search(text) and len(numbers) == 1 and WAIST_CM[0] <= numbers[0] <= WAIST_CM[1]:
        return numbers[0]
    return None


def _float(number: str) -> float:
    return float(number.replace(",", "."))


def _waist_reminder_open(coach: "Coach", now: datetime.datetime) -> bool:
    """A waist reminder went out for the latest due date and no value came since."""
    phase = phases.active(coach)
    if phase is None:
        return False
    m = phases.params(coach)["measurements"]
    today = now.date()
    due = [d["date"] for d in measurements_due(coach, today - datetime.timedelta(days=m["waist_every_weeks"] * 7 - 1),
                                               today) if d["kind"] == "waist"]
    if not due:
        return False
    sent = coach.db.value("SELECT 1 FROM once_keys WHERE key = ?",
                          (f"measurement-reminder:{phase['id']}:waist:{due[-1]}",))
    return bool(sent) and not received_since(coach, "waist", due[-1])


def waist_values(coach: "Coach") -> list[dict[str, Any]]:
    """Every stored waist value, oldest first: [{"date", "cm"}]."""
    return [{"date": r["date"], "cm": r["cm"]}
            for r in coach.db.all("SELECT date, cm FROM waist_measurements ORDER BY date, id")]


def waist_history(coach: "Coach", day: Date) -> list[dict[str, Any]]:
    """Waist values up to `day`, newest first: the stored values (`source`
    "measured") and each phase's start value (setup value `waist_cm_start`,
    `source` "phase_start") on its start date, unless a value was measured
    that day."""
    values = [{**w, "source": "measured"} for w in waist_values(coach) if w["date"] <= day.isoformat()]
    measured = {w["date"] for w in values}
    for row in coach.db.all("SELECT start_date, setup FROM phases WHERE start_date <= ? ORDER BY start_date",
                            (day.isoformat(),)):
        start = json.loads(row["setup"]).get("waist_cm_start")
        if start is not None and row["start_date"] not in measured:
            values.append({"date": row["start_date"], "cm": start, "source": "phase_start"})
    return sorted(values, key=lambda w: w["date"], reverse=True)


WAIST_HISTORY_LIMIT = 12  # values when the model gives no limit, as the web page's weight detail


@registry.tool(
    "waist_history",
    "The user's waist measurements up to today, newest first: date, cm, and `source` (`measured`: a value the "
    "user sent; `phase_start`: the waist recorded in a phase's setup, on its start date). `limit` = how many of "
    f"the newest values (default {WAIST_HISTORY_LIMIT}).",
    {
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
        "additionalProperties": False,
    },
)
async def waist_history_tool(coach: "Coach", args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    return {"waist": waist_history(coach, now.date())[:args.get("limit", WAIST_HISTORY_LIMIT)]}


# --- photos ----------------------------------------------------------------------


@registry.photo()
async def photo(coach: "Coach", data: bytes, caption: str | None, now: datetime.datetime) -> bool:
    day = now.date().isoformat()
    number = coach.db.value("SELECT COUNT(*) FROM photos WHERE set_date = ?", (day,)) + 1
    folder = coach.state_dir / PHOTOS_DIR / day
    folder.mkdir(parents=True, exist_ok=True)
    while (folder / f"{number}.jpg").exists():
        number += 1
    path = folder / f"{number}.jpg"
    path.write_bytes(data)
    coach.db.execute("INSERT INTO photos (set_date, path, caption, received_at) VALUES (?, ?, ?, ?)",
                     (day, path.relative_to(coach.state_dir).as_posix(), caption, now.isoformat(timespec="seconds")))
    coach.say(f"📸 Saved photo {number} of the {day} set.")
    return True


def photo_sets(coach: "Coach") -> list[dict[str, Any]]:
    """Every stored photo set, oldest first: [{"date", "photos": [{"path",
    "caption", "received_at"}]}]; `path` is relative to `coach.state_dir`."""
    sets: dict[str, list[dict[str, Any]]] = {}
    for r in coach.db.all("SELECT set_date, path, caption, received_at FROM photos ORDER BY set_date, id"):
        sets.setdefault(r["set_date"], []).append(
            {"path": r["path"], "caption": r["caption"], "received_at": r["received_at"]})
    return [{"date": day, "photos": photos} for day, photos in sets.items()]


def photo_file(coach: "Coach", set_date: str, number: int) -> Path | None:
    """The stored file of photo `number` (1-based, in arrival order) of the
    `set_date` set, or None. Only paths from the photos table, and only
    inside the coach's photos directory."""
    if number < 1:
        return None
    row = coach.db.one("SELECT path FROM photos WHERE set_date = ? ORDER BY id LIMIT 1 OFFSET ?",
                       (set_date, number - 1))
    if row is None:
        return None
    root = (coach.state_dir / PHOTOS_DIR).resolve()
    path = (coach.state_dir / row["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    return path
