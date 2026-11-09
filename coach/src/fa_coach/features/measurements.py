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
- Reminder job: from `REMINDER_TIME` on a due date, one message asks for
  what is due (photos with the protocol); sent once per due date, or late
  (still once) if the coach was down, unless the value already came in.
- Photos sent to the chat are stored under the coach's state directory as
  `photos/<date>/<n>.jpg`, one set per day, and acknowledged. Waist values
  ("waist 84.5", or a bare "84.5" while a waist reminder is open) are stored
  with their date. Read them with `photo_sets(coach)` and `waist_values(coach)`.
  Photos are kept whenever they arrive, even with photos off.
"""

import datetime
import re
from typing import TYPE_CHECKING, Any

from .. import phases
from ..registry import registry

if TYPE_CHECKING:
    from ..core import Coach

Date = datetime.date
KINDS = ("waist", "photos")
REMINDER_TIME = datetime.time(7, 0)  # assumption: morning of the due date, before breakfast

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
    if now.time() < REMINDER_TIME:
        today -= datetime.timedelta(days=1)
    m = phases.params(coach)["measurements"]
    longest = max(m["waist_every_weeks"], m["photos_every_weeks"]) * 7
    latest: dict[str, str] = {}
    for item in measurements_due(coach, today - datetime.timedelta(days=longest - 1), today):
        latest[item["kind"]] = item["date"]  # in date order: the last one wins
    asked = [kind for kind, due in sorted(latest.items(), key=lambda kv: KINDS.index(kv[0]))
             if not _received_since(coach, kind, due)
             and coach.db.once(f"measurement-reminder:{phase['id']}:{kind}:{due}", now)]
    if asked:
        coach.say(_reminder_text(asked))


def _received_since(coach: "Coach", kind: str, day: str) -> bool:
    table, column = ("waist_measurements", "date") if kind == "waist" else ("photos", "set_date")
    return coach.db.value(f"SELECT COUNT(*) FROM {table} WHERE {column} >= ?", (day,)) > 0


def _reminder_text(kinds: list[str]) -> str:
    lines = ["📏 Check-in day."]
    if "waist" in kinds:
        lines.append("Send your waist measurement in cm, e.g. \"waist 84.5\".")
    if "photos" in kinds:
        lines.append(f"Send your progress photo set here. Photo protocol: {PHOTO_PROTOCOL}")
    return "\n".join(lines)



# --- waist -----------------------------------------------------------------------


@registry.text(order=60)
async def waist_text(coach: "Coach", text: str, now: datetime.datetime) -> bool:
    cm = _waist_in(text, coach, now)
    if cm is None:
        return False
    if not WAIST_CM[0] <= cm <= WAIST_CM[1]:
        coach.say(f"{cm:g} cm doesn't look like a waist measurement; send it in cm, e.g. \"waist 84.5\".")
        return True
    day = now.date().isoformat()
    coach.db.execute("INSERT INTO waist_measurements (date, cm, created_at) VALUES (?, ?, ?)",
                     (day, cm, now.isoformat(timespec="seconds")))
    coach.say(f"📏 Saved: waist {cm:g} cm on {day}.")
    return True


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
    return bool(sent) and not _received_since(coach, "waist", due[-1])


def waist_values(coach: "Coach") -> list[dict[str, Any]]:
    """Every stored waist value, oldest first: [{"date", "cm"}]."""
    return [{"date": r["date"], "cm": r["cm"]}
            for r in coach.db.all("SELECT date, cm FROM waist_measurements ORDER BY date, id")]


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
