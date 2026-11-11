"""Home's banner (coach-web ticket 05): only on today, and only when
something needs the user: an open proposal (the page links to the Week page,
where it is shown read-only; it is approved in Telegram) or coach questions
waiting for a tap in Telegram (a day question asked and not answered, a
"was this a reset?" question still open). Null otherwise.
"""

import datetime
from typing import Any

from .. import proposals, views
from ..registry import registry


@registry.view_part("home", "banner", schema="web_home_banner", order=5)
def banner(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any] | None:
    if views.day(query, now) != now.date():
        return None
    open_ = proposals.open_proposals(coach)
    questions = (coach.db.value("SELECT COUNT(*) FROM day_questions WHERE status = 'asked'")
                 + coach.db.value("SELECT COUNT(*) FROM reset_questions WHERE status = 'open'"))
    if not open_ and not questions:
        return None
    proposal = None
    if open_:
        latest = open_[-1]
        proposal = {"id": latest["id"], "type": latest["type"], "change": proposals.describe_change(latest)}
    return {"proposal": proposal, "questions": questions}
