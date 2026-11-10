"""Live read-only MFP and Hevy tools for the model (ticket 16): listed from
the api at start-up (the first sync), and offered to every task that gets all
tools (the coach chat). See `fa_coach/live_tools.py`."""

import datetime

from .. import live_tools
from ..registry import registry


@registry.syncer("live_tools", order=0)
async def list_at_start(coach, now: datetime.datetime) -> None:
    await live_tools.ensure_listed(coach, now)


@registry.tool_source("live")
async def live(coach, now: datetime.datetime):
    return await live_tools.tools(coach, now)
