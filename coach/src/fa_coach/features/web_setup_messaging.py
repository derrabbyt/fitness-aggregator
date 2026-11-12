"""Setup › Messaging (coach-web ticket 10): when the coach writes. The weekly
check-in (weekday and time), the evening reminder time, the daily limit of
unprompted messages and the step-floor window (`soft_floor_min_days`). Each
saves directly (`setup/messaging` {field, value}), through chat's
`record_setup_value` with the `logistics.<field>` key.
"""

import datetime
from typing import Any

from .. import phases, views
from ..registry import registry
from . import web_setup

FIELDS = ("weekly_checkin", "evening_reminder_time", "max_unprompted_messages_per_day", "soft_floor_min_days")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _values(coach) -> dict[str, Any]:
    p = phases.params(coach)
    m = p["messaging"]
    return {"weekly_checkin": m.get("weekly_checkin"), "evening_reminder_time": m.get("evening_reminder_time"),
            "max_unprompted_messages_per_day": m.get("max_unprompted_messages_per_day"),
            "soft_floor_min_days": p["activity"].get("soft_floor_min_days")}


@registry.view_part("setup", "messaging", schema="web_setup_summary", order=30)
def summary(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    v = _values(coach)
    check_in = v["weekly_checkin"]
    limit = v["max_unprompted_messages_per_day"]
    parts = [
        f"Check-in {check_in[:1].upper()}{check_in[1:]}" if check_in else "No check-in day",
        f"reminder {v['evening_reminder_time']}" if v["evening_reminder_time"] else "no evening reminder",
        f"{limit} message{'' if limit == 1 else 's'} a day" if limit else "no message limit",
    ]
    return {"summary": " · ".join(parts)}


@registry.view("setup/messaging", schema="web_setup_messaging")
def messaging(coach, query: dict[str, str], now: datetime.datetime) -> dict[str, Any]:
    v = _values(coach)
    check_in = v["weekly_checkin"]
    day, _, time = check_in.partition(" ") if check_in else (None, None, None)
    return {
        "editable": web_setup.editable(coach),
        "weekly_checkin": {"day": day, "time": time} if check_in else None,
        "evening_reminder_time": v["evening_reminder_time"],
        "max_unprompted_messages_per_day": v["max_unprompted_messages_per_day"],
        "soft_floor_min_days": v["soft_floor_min_days"],
    }


@registry.web_command("setup/messaging")
async def set_messaging(coach, body: dict[str, Any], now: datetime.datetime) -> dict[str, Any]:
    """{field, value}: one messaging value (field: weekly_checkin as 'sun 18:00',
    evening_reminder_time 'HH:MM', max_unprompted_messages_per_day,
    soft_floor_min_days; null clears it). Returns the section."""
    web_setup.require_editable(coach)
    name = views.field(body, "field")
    if name not in FIELDS:
        raise views.WebError(400, f"{name!r} isn't a messaging value ({', '.join(FIELDS)}).")
    value = views.field(body, "value")
    await views.run_tool(coach, "record_setup_value", {"key": f"logistics.{name}", "value": value}, now)
    return messaging(coach, {}, now)
