"""Fakes for the Coach seam: api client, model client, clock and outbox.

Extend these as tickets need: the fake api grows methods that return canned
records and record writes, the fake model returns scripted replies.
"""

import datetime
import itertools
import json
from typing import Any

from fa_coach.ports import Edit, ModelReply, ModelRequest, Outgoing, Send, ToolCall, ToolResult

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
    """Returns scripted replies in order and records every request it was
    given (one request per model turn, so a tool loop records several)."""

    def __init__(self, *replies: ModelReply | Exception) -> None:
        self.replies: list[ModelReply | Exception] = list(replies)
        self.requests: list[ModelRequest] = []

    def script(self, *replies: ModelReply | Exception) -> None:
        self.replies.extend(replies)

    async def run(self, request: ModelRequest) -> ModelReply:
        self.requests.append(request)
        if not self.replies:
            raise AssertionError(f"unexpected model call: {request.task_skills}")
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def results(self, n: int) -> list[ToolResult]:
        """The tool results code sent back for the tool calls of the n-th
        recorded model turn (0-based, counted over all requests)."""
        reply, results = self.requests[n + 1].steps[-1]
        assert reply.tool_calls, f"model turn {n} called no tools"
        return list(results)


def reply(text: str) -> ModelReply:
    return ModelReply(text=text)


def reply_json(data: Any) -> ModelReply:
    return ModelReply(text=json.dumps(data))


_ids = itertools.count(1)


def tool_call(name: str, **args: Any) -> ModelReply:
    """A model turn that calls one tool."""
    return tool_calls((name, args))


def tool_calls(*calls: tuple[str, dict[str, Any]]) -> ModelReply:
    """A model turn that calls several tools at once."""
    return ModelReply(
        tool_calls=tuple(ToolCall(f"call_{next(_ids)}", name, args) for name, args in calls), stop_reason="tool_use"
    )


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
