"""Photo review and body-fat estimates (coach-reviews ticket 04; spec, "Photo
review"). Skill `photo-review`, output `photo_review.schema.json`.

- Job `photo-review`: once the latest photo set has arrived (no new photo for
  `SETTLE`; photos come one by one) during the active phase, with photos on,
  and the set is fresh (`FRESH_DAYS`), the decision model gets that set and
  one earlier set as images, the latest estimate before it and the waist
  trend. Once per set date; a model failure (an error or no usable answer)
  is tried again on later runs, at most `MAX_ATTEMPTS` times per set (one
  `once` key per attempt), then it is given up and logged.
- Like for like (`comparison_set`): the most recent earlier set whose
  estimate (`body_fat.on`, the user's winning) is within `LIKE_FOR_LIKE_PCT`
  of the latest estimate up to the new set's date; without one, the phase
  start set (the first set on or after the start date); else none.
- Code stores the range's midpoint as the set date's estimate (source
  model, `body_fat.add`) and sends the review (`reviews.send`, kind photo,
  key the set date): the model's `notes` plus the range.
- Chat tool `record_body_fat(pct, date)`: the user's own estimate, which wins
  for its date (`body_fat.on`).
- Advice (`advise_if_due`): when the newest estimate (photo or the user's)
  reaches the active phase's `body_fat.advise_near_pct` low end (23 % in a
  bulk; null in a cut or maintenance), one message suggests a mini-cut or
  ending the bulk, as advice only, at most once per `ADVICE_EVERY`. Sent
  exempt from the daily limit (kind `ADVICE_KIND`, which is also how the
  4-week limit is counted).
"""

import datetime
import logging
from typing import TYPE_CHECKING, Any

from .. import body_fat, messaging, phases, reviews
from ..ask import ToolError
from ..ports import Image, ModelError
from ..registry import registry
from . import measurements

if TYPE_CHECKING:
    from ..core import Coach

logger = logging.getLogger("fa-coach")

Date = datetime.date
SKILL = "photo-review"
KIND = "photo"
MAX_ATTEMPTS = 3  # a set whose review the model fails is tried again on later runs, at most this often
SETTLE = datetime.timedelta(minutes=10)  # assumption: a set is complete 10 minutes after its last photo
FRESH_DAYS = 2  # a set dated more than this many days back gets no review (no backlog after a deploy)
LIKE_FOR_LIKE_PCT = 2.0  # spec: similar leanness = estimates within +-2 % body fat
ADVICE_EVERY = datetime.timedelta(weeks=4)
ADVICE_KIND = "body-fat-advice"
WAIST_VALUES = 6  # the newest waist values the review sees


# --- the review --------------------------------------------------------------------


@registry.job("photo-review", order=60)
async def photo_review(coach: "Coach", now: datetime.datetime) -> None:
    phase = phases.active(coach)
    if phase is None or not phases.params(coach)["measurements"]["photos_enabled"]:
        return
    sets = measurements.photo_sets(coach)
    if not sets:
        return
    new = sets[-1]
    day = new["date"]
    if day < phase["start_date"] or Date.fromisoformat(day) < now.date() - datetime.timedelta(days=FRESH_DAYS):
        return
    last = max(datetime.datetime.fromisoformat(p["received_at"]) for p in new["photos"])
    if now - last < SETTLE:
        return
    if reviews.sent(coach, KIND, day):
        return
    attempt = next((n for n in range(1, MAX_ATTEMPTS + 1) if coach.db.once(_attempt_key(day, n), now)), None)
    if attempt is None:
        return
    if not await _review(coach, phase, new, sets[:-1], now) and attempt == MAX_ATTEMPTS:
        logger.error("photo review %s: no usable answer after %d attempts, giving up", day, MAX_ATTEMPTS)


def _attempt_key(day: str, n: int) -> str:
    return f"photo-review:{day}" if n == 1 else f"photo-review:{day}:{n}"


def comparison_set(coach: "Coach", phase: dict[str, Any], day: str,
                   earlier: list[dict[str, Any]]) -> tuple[dict[str, Any], str] | None:
    """(set, "similar_leanness" | "phase_start") to compare the `day` set with, or None."""
    reference = body_fat.latest(coach, day)
    if reference is not None:
        for photo_set in reversed(earlier):
            estimate = body_fat.on(coach, photo_set["date"])
            if estimate is not None and abs(estimate["pct"] - reference["pct"]) <= LIKE_FOR_LIKE_PCT:
                return photo_set, "similar_leanness"
    start = next((s for s in earlier if s["date"] >= phase["start_date"]), None)
    return (start, "phase_start") if start is not None else None


async def _review(coach: "Coach", phase: dict[str, Any], new: dict[str, Any], earlier: list[dict[str, Any]],
                  now: datetime.datetime) -> bool:
    """Ask the model and send the review; False when the model gave no usable answer (retried)."""
    day = new["date"]
    picked = comparison_set(coach, phase, day, earlier)
    shown = images(coach, "New set", new)
    compared = None
    if picked is not None:
        old, why = picked
        shown += images(coach, "Comparison set", old)
        compared = {"id": old["date"], "date": old["date"], "photos": len(old["photos"]), "picked": why,
                    "estimate": body_fat.on(coach, old["date"])}
    p = phases.params(coach)
    facts = {
        "photo_set": {"id": day, "date": day, "photos": len(new["photos"]),
                      "phase_week": phases.phase_week(phase, Date.fromisoformat(day))},
        "comparison_set": compared,
        "previous_estimate": body_fat.latest(coach, day),
        "waist": measurements.waist_history(coach, Date.fromisoformat(day))[:WAIST_VALUES],
        "phase": {"phase_id": phase["phase_id"], "start_date": phase["start_date"]},
        "params": {"body_fat": p.get("body_fat"), "measurements": p["measurements"]},
    }
    try:
        answer = await coach.ask([SKILL], facts, tools=(), output_schema="photo_review", decision=True,
                                 images=shown, now=now)
    except ModelError as exc:
        logger.warning("photo review %s: %s", day, exc)
        return False
    if not answer.ok:
        logger.warning("photo review %s: no usable answer: %s", day, "; ".join(answer.errors))
        return False
    review = answer.data
    low, high = sorted((review["bf_estimate"]["low_pct"], review["bf_estimate"]["high_pct"]))
    pct = round((low + high) / 2 * 2) / 2  # the range's midpoint, to the half percent
    review_id = reviews.send(
        coach, kind=KIND, key=day, phase_row_id=phase["id"],
        period_start=compared["date"] if compared else day, period_end=day,
        facts={**facts, "review": review, "estimate_pct": pct}, text=_text(review, low, high, compared), now=now)
    if review_id is None:
        return True
    body_fat.add(coach, day, pct, "model", now, review_id=review_id)
    advise_if_due(coach, day, now)
    return True


def images(coach: "Coach", label: str, photo_set: dict[str, Any]) -> list[Image]:
    out = []
    for n, photo in enumerate(photo_set["photos"], start=1):
        data = (coach.state_dir / photo["path"]).read_bytes()
        media_type = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
        out.append(Image(f"{label} {photo_set['date']}, photo {n}", data, media_type))
    return out


def _text(review: dict[str, Any], low: float, high: float, compared: dict[str, Any] | None) -> str:
    against = (f"compared with the {compared['date']} set" if compared else "no earlier set to compare with")
    return (f"📸 Photo review\n\n{review['notes'].strip()}\n\n"
            f"Body-fat estimate: {low:g}–{high:g} % ({review['confidence']} confidence; {against}).")


# --- advice ------------------------------------------------------------------------


def advise_if_due(coach: "Coach", day: str, now: datetime.datetime) -> bool:
    """Send the mini-cut / end-of-bulk advice when the newest estimate is the
    one for `day` and at the phase's advice level, unless it went out within
    `ADVICE_EVERY`. Returns whether it was sent."""
    if phases.active(coach) is None:
        return False
    near = phases.params(coach).get("body_fat", {}).get("advise_near_pct")
    newest = body_fat.estimates(coach)
    if not near or not newest or newest[0]["date"] != day or newest[0]["pct"] < near[0]:
        return False
    last = messaging.last_sent_at(coach, ADVICE_KIND)
    if last is not None and now - last < ADVICE_EVERY:
        return False
    estimate = newest[0]
    whose = "your own estimate" if estimate["source"] == "user" else "from your photos"
    text = (f"🧭 Body fat is about {estimate['pct']:g} % ({whose}). Around {near[0]:g}–{near[1]:g} % is where a "
            "mini-cut or ending the bulk is worth considering. It's advice, not a stop: you can keep going, "
            "or say \"start cut\" when you want one.")
    return messaging.send(coach, text, now, kind=ADVICE_KIND, exempt=True)


# --- the user's own estimate -------------------------------------------------------


@registry.tool(
    "record_body_fat",
    "Store the user's own body-fat estimate in % (never a scale's reading) for a date (default today). It wins "
    "over the photo estimate for that date. Returns what was stored, the photo estimate it overrides (if any) "
    "and whether code sent the mini-cut / end-of-bulk advice.",
    {
        "type": "object",
        "properties": {"pct": {"type": "number"}, "date": {"type": "string", "format": "date"}},
        "required": ["pct"],
        "additionalProperties": False,
    },
)
async def record_body_fat(coach: "Coach", args: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    pct, day = args["pct"], args.get("date", now.date().isoformat())
    if (why := body_fat.problem(pct)) is not None:
        raise ToolError(why)
    if day > now.date().isoformat():
        raise ToolError(f"{day} is in the future.")
    body_fat.add(coach, day, pct, "user", now)
    stored = body_fat.on(coach, day)
    return {"recorded": {"date": day, "pct": pct}, "photo_estimate_pct": stored["model_pct"],
            "advice_sent": advise_if_due(coach, day, now)}
