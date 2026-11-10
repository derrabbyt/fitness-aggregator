"""One model task, run to the end: `Coach.ask(...)`.

Builds the request (cached prefix: coach-core + active phase skill + tool
definitions; then the task skills, a short state snapshot and the input),
then loops: the model either answers, or calls registered tools, which code
validates and runs once each, sending the results back. With
`output_schema`, the final text must be one JSON object valid against that
schema; anything else comes back as `errors` and is not acted on.
"""

import datetime
import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator, FormatChecker

from .ports import ChatTurn, ModelRequest, ToolCall, ToolResult

if TYPE_CHECKING:
    from .core import Coach

logger = logging.getLogger("fa-coach")

CORE_SKILL = "coach-core"
MAX_TURNS = 8  # model turns per task; a loop that doesn't settle stops here


@dataclass(frozen=True)
class Executed:
    """A tool call code ran, and what it returned."""

    name: str
    args: dict[str, Any]
    result: Any
    is_error: bool = False


@dataclass
class Answer:
    text: str = ""
    data: Any = None  # the validated JSON object, when an output schema was asked for
    errors: list[str] = field(default_factory=list)  # why `data` is missing
    calls: list[Executed] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


async def ask(
    coach: "Coach",
    task_skills: Sequence[str],
    input: Any = None,
    *,
    tools: Iterable[str] | None = None,
    output_schema: str | None = None,
    decision: bool = False,
    history: Sequence[ChatTurn] = (),
    phase: str | None = None,
    now: datetime.datetime | None = None,
) -> Answer:
    now = now or coach.clock.now()
    phase_id = phase or coach.active_phase_id()
    prefix = (CORE_SKILL,) + ((coach.skills.phase_skill_name(phase_id),) if phase_id else ())
    allowed = await _tools(coach, tools, now)
    request = ModelRequest(
        prefix_skills=prefix,
        task_skills=tuple(task_skills),
        input=input,
        state=coach.state_snapshot(now),
        tools=tuple(t.definition() for t in allowed.values()),
        history=tuple(history),
        output_schema=output_schema,
        decision=decision,
    )
    answer = Answer()
    for _ in range(MAX_TURNS):
        reply = await coach.model.run(request)
        if not reply.tool_calls:
            answer.text = reply.text.strip()
            if reply.stop_reason == "refusal":
                answer.errors.append("the model declined to answer")
            elif output_schema is not None:
                answer.data, answer.errors = _parse(coach, answer.text, output_schema)
            return answer
        results = []
        for call in reply.tool_calls:
            executed = await _run_tool(coach, allowed, call, now)
            answer.calls.append(executed)
            results.append(ToolResult(call.id, executed.result, executed.is_error))
        request = _with_step(request, reply, tuple(results))
    answer.errors.append(f"no answer after {MAX_TURNS} model turns")
    return answer


async def _tools(coach: "Coach", names: Iterable[str] | None, now: datetime.datetime) -> dict:
    """The tools for one task: registered ones, plus runtime tools from the
    registry's tool sources (live reads) when the task gets every tool
    (`names` None) or names one that isn't registered. A registered name
    always wins over a runtime tool of the same name."""
    available = dict(coach.registry.tools)
    names = None if names is None else list(names)
    if names is None or any(n not in available for n in names):
        for source in coach.registry.tool_sources:
            try:
                runtime = await source.fn(coach, now)
            except Exception:  # noqa: BLE001 - the task runs without that source's tools
                logger.exception("tool source %s failed", source.name)
                continue
            for tool in runtime:
                available.setdefault(tool.name, tool)
    if names is None:
        names = list(available)
    missing = [n for n in names if n not in available]
    if missing:
        raise KeyError(f"unknown tools: {missing}")
    # Sorted, so the tool definitions (part of the cached prefix) are stable.
    return {name: available[name] for name in sorted(names)}


async def _run_tool(coach: "Coach", allowed: dict, call: ToolCall, now: datetime.datetime) -> Executed:
    tool = allowed.get(call.name)
    if tool is None:
        return Executed(call.name, call.args, {"error": f"no tool named {call.name!r}"}, True)
    problems = [
        f"{'/'.join(map(str, e.absolute_path)) or '(input)'}: {e.message}"
        for e in Draft202012Validator(tool.input_schema, format_checker=FormatChecker()).iter_errors(call.args)
    ]
    if problems:
        return Executed(call.name, call.args, {"error": "invalid input", "details": problems}, True)
    try:
        result = await tool.fn(coach, call.args, now)
    except ToolError as exc:
        return Executed(call.name, call.args, {"error": str(exc)}, True)
    except Exception as exc:  # noqa: BLE001 - reported to the model, never retried by code
        logger.exception("tool %s failed", call.name)
        return Executed(call.name, call.args, {"error": f"{type(exc).__name__}: the tool failed"}, True)
    return Executed(call.name, call.args, result)


class ToolError(Exception):
    """Raised by a tool for a request it refuses (bad dates, unknown id).
    The message goes back to the model."""


def _with_step(request: ModelRequest, reply, results: tuple[ToolResult, ...]) -> ModelRequest:
    return replace(request, steps=request.steps + ((reply, results),))


def _parse(coach: "Coach", text: str, schema: str) -> tuple[Any, list[str]]:
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1] if "\n" in body else ""
        body = body.rsplit("```", 1)[0]
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        return None, [f"not JSON: {exc.msg}"]
    errors = coach.skills.errors(data, schema)
    return (None, errors) if errors else (data, [])
