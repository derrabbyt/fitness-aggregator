"""`coach.ask`: the model gets the cached prefix, task skills, state snapshot
and input; tool calls are validated and executed by code, once each, and
their results go back to the model; a schema-validated JSON object comes
back as `data`, anything invalid as `errors`."""

from fa_coach.ports import ModelReply
from fa_coach.registry import Registry
from fakes import reply, reply_json, tool_call, tool_calls

NOTE = {
    "id": "n_1",
    "created_at": "2026-11-09T09:00:00+01:00",
    "text": "ate out",
    "applies_from": "2026-11-09",
    "applies_to": "2026-11-09",
    "tags": ["salty_or_large_meal"],
    "suggest_unusable": "no",
}


def counting_tool(registry: Registry, seen: list) -> None:
    @registry.tool(
        "count",
        "Count something",
        {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"], "additionalProperties": False},
    )
    async def count(coach, args, now):
        seen.append(args["n"])
        return {"counted": args["n"]}


async def test_tool_calls_are_executed_by_code_and_their_results_go_back(make_coach, model):
    registry, seen = Registry(), []
    counting_tool(registry, seen)
    model.script(tool_calls(("count", {"n": 1}), ("count", {"n": 2})), reply("Counted twice."))

    answer = await make_coach(registry=registry).ask(["coach-chat"], {"q": "count"})

    assert seen == [1, 2]
    assert [r.content for r in model.results(0)] == [{"counted": 1}, {"counted": 2}]
    assert answer.text == "Counted twice."
    assert len(model.requests) == 2


async def test_invalid_or_unknown_tool_calls_are_refused_not_run(make_coach, model):
    registry, seen = Registry(), []
    counting_tool(registry, seen)
    model.script(tool_calls(("count", {"n": "two"}), ("set_goal", {"kcal": 3000})), reply("Sorry."))

    await make_coach(registry=registry).ask(["coach-chat"], tools=["count"])

    assert seen == []
    assert [r.is_error for r in model.results(0)] == [True, True]


async def test_only_the_named_tools_are_offered_and_called(make_coach, model):
    registry, seen = Registry(), []
    counting_tool(registry, seen)

    @registry.tool("other", "Other", {"type": "object"})
    async def other(coach, args, now):
        seen.append("other")

    model.script(tool_call("other"), reply("Done."))

    await make_coach(registry=registry).ask(["weekly-report"], tools=["count"])

    assert [t["name"] for t in model.requests[0].tools] == ["count"]
    assert seen == []
    assert model.results(0)[0].is_error


async def test_a_failing_tool_is_reported_to_the_model_and_not_retried(make_coach, model):
    registry, calls = Registry(), []

    @registry.tool("flaky", "Fails", {"type": "object"})
    async def flaky(coach, args, now):
        calls.append(1)
        raise RuntimeError("502 Bad Gateway")

    model.script(tool_call("flaky"), reply("That didn't work."))

    answer = await make_coach(registry=registry).ask(["coach-chat"])

    assert calls == [1]
    assert model.results(0)[0].is_error
    assert answer.text == "That didn't work."


async def test_a_schema_valid_json_answer_comes_back_as_data(coach, model):
    model.script(reply_json(NOTE))

    answer = await coach.ask(["context-log"], {"message": "ate out"}, tools=(), output_schema="context_note")

    assert answer.ok
    assert answer.data == NOTE
    assert model.requests[0].output_schema == "context_note"


async def test_an_invalid_json_answer_is_not_data(coach, model):
    model.script(reply_json({**NOTE, "tags": ["pizza"]}), reply("not json at all"))

    wrong_schema = await coach.ask(["context-log"], tools=(), output_schema="context_note")
    not_json = await coach.ask(["context-log"], tools=(), output_schema="context_note")

    assert wrong_schema.data is None and any("tags" in e for e in wrong_schema.errors)
    assert not_json.data is None and not_json.errors


async def test_a_refusal_is_not_an_answer(coach, model):
    model.script(ModelReply(text="", stop_reason="refusal"))

    answer = await coach.ask(["weekly-decision"], tools=(), output_schema="weekly_verdict", decision=True)

    assert not answer.ok and answer.data is None
    assert model.requests[0].decision


async def test_a_tool_loop_that_never_settles_stops(make_coach, model):
    registry, seen = Registry(), []
    counting_tool(registry, seen)
    model.script(*[tool_call("count", n=i) for i in range(20)])

    answer = await make_coach(registry=registry).ask(["coach-chat"])

    assert not answer.ok
    assert len(seen) < 20


async def test_the_state_snapshot_carries_the_date(coach, model, clock):
    model.script(reply("ok"))

    await coach.ask(["coach-chat"], tools=())

    state = model.requests[0].state
    assert state["today"] == "2026-11-09"
    assert state["weekday"] == "Monday"
