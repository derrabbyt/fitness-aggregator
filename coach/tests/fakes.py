"""Fakes for the Coach seam: api client, model client, clock and outbox.

Extend these as tickets need: the fake api grows methods that return canned
records and record writes, the fake model returns scripted replies.
"""

import datetime
from typing import Any

from fa_coach.ports import Edit, ModelReply, ModelRequest, Outgoing, Send

TZ = datetime.timezone(datetime.timedelta(hours=1))  # Europe/Vienna in winter


class FakeClock:
    def __init__(self, start: datetime.datetime = datetime.datetime(2026, 11, 9, 9, 0, tzinfo=TZ)):
        self.current = start

    def now(self) -> datetime.datetime:
        return self.current

    def advance(self, **delta: float) -> datetime.datetime:
        self.current += datetime.timedelta(**delta)
        return self.current


class FakeApi:
    """Records every call as (name, args)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []


class FakeModel:
    """Returns scripted replies in order and records every request it was given."""

    def __init__(self, *replies: ModelReply) -> None:
        self.replies = list(replies)
        self.requests: list[ModelRequest] = []

    async def run(self, request: ModelRequest) -> ModelReply:
        self.requests.append(request)
        if not self.replies:
            raise AssertionError(f"unexpected model call: {request.task_skill}")
        return self.replies.pop(0)


class FakeOutbox:
    def __init__(self) -> None:
        self.items: list[Outgoing] = []

    def put(self, item: Outgoing) -> None:
        self.items.append(item)

    @property
    def sent(self) -> list[Send]:
        return [i for i in self.items if isinstance(i, Send)]

    @property
    def texts(self) -> list[str]:
        return [i.text for i in self.sent]

    @property
    def edits(self) -> list[Edit]:
        return [i for i in self.items if isinstance(i, Edit)]

    def clear(self) -> None:
        self.items.clear()
