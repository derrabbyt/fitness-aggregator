"""A mini-cut's end date (skill phase-cut, CUT-END): from the day after the
active phase's setup value `end_date`, at ASK_HOUR or later, the coach sends
the end card (features/phase_end.py) once per end date. Confirm ends the
phase with its last day yesterday; Cancel keeps it going (moving `end_date`
asks again after the new date).
"""

import datetime

from .. import phases
from ..registry import registry
from . import phase_end

ASK_HOUR = 9  # not in the night


@registry.job("cut-end-date", order=60)
async def end_date_job(coach, now: datetime.datetime) -> None:
    phase = phases.active(coach)
    end = phase and phase["setup"].get("end_date")
    if not end or now.date() <= datetime.date.fromisoformat(end) or now.hour < ASK_HOUR:
        return
    if not coach.db.once(f"cut-end-date:{phase['id']}:{end}", now):
        return
    phase_end.send_card(coach, phase_end.MODE_END, f"the end date {end} was reached", now)
