"""The MFP goal on phase confirm (ticket 06): once a phase start is stored,
code sets the MFP goal to the confirmed base maintenance + surplus (a rest
day; activity comes on top) and macros at that kcal
(`mfp_goal.set_once`: sent once, read back once, never retried) and adds a
line to the confirmation card saying whether MFP now shows it. Whatever MFP
does, the phase stays active and the coach targets stay as confirmed.
"""

import datetime
from typing import Any

from .. import mfp_goal, phases


@phases.on_confirmed
async def set_mfp_goal(coach, phase: dict[str, Any], now: datetime.datetime) -> str | None:
    targets = phases.targets(coach, datetime.date.fromisoformat(phase["start_date"]))
    if targets is None:
        return None
    result = await mfp_goal.set_once(coach, f"phase-start:{phase['id']}", targets["mfp_goal"], now)
    return mfp_goal.describe(result) if result else None
