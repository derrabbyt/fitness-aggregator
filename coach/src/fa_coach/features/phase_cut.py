"""The cut (skill phase-cut) in the weekly check-in and at its end date.
Its numbers (deficit, target rate, band) are in fa_coach/cut.py.

- The decision guard's rule (`weekly_checkin.phase_expected_change`): the
  core's (slower than the band, i.e. stalled: eat less, the small or large
  step by the distance from the band; in the band: hold), except that faster
  than the band always calls for `decisions.increase_step_kcal` more (CUT-FAST).
- A mini-cut's end date (CUT-END): from the day after the active phase's
  setup value `end_date`, at ASK_HOUR or later, the coach sends the end card
  (features/phase_end.py) once per end date. Confirm ends the phase with its
  last day yesterday; Cancel keeps it going (a moved `end_date` asks again
  after the new date).
"""

import datetime
from typing import Any

from .. import cut, phases
from ..registry import registry
from . import phase_end, weekly_checkin

ASK_HOUR = 9  # not in the night


def expected_change(weight: dict[str, Any], decisions: dict[str, Any]) -> tuple[str, float | None, str | None, str]:
    want, step, size, why = weekly_checkin.expected_change(weight, decisions)
    if want == "increase":
        return want, decisions["increase_step_kcal"], "small", why
    return want, step, size, why


weekly_checkin.phase_expected_change[cut.PHASE_ID] = expected_change


@registry.job("cut-end-date", order=60)
async def end_date_job(coach, now: datetime.datetime) -> None:
    phase = phases.active(coach)
    end = phase and phase["setup"].get("end_date")
    if not end or now.date() <= datetime.date.fromisoformat(end) or now.hour < ASK_HOUR:
        return
    if not coach.db.once(f"cut-end-date:{phase['id']}:{end}", now):
        return
    phase_end.send_card(coach, phase_end.MODE_END, f"the end date {end} was reached", now)
