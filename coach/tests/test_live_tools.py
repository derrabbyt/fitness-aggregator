"""Live read-only MFP and Hevy tools (ticket 16): the chat model can look
things up through the api's MCP tools, listed from the api at start-up and
filtered by the coach's read-only allowlist; no write tool is ever offered."""

import pytest

from fa_coach import live_tools
from fakes import reply, tool_call

WRITES = ("log_", "delete", "modify", "clear", "write", "set_", "quick_add", "add_", "draft", "goal")


def mcp_tool(name: str, **properties) -> dict:
    return {"name": name, "description": f"{name} (from the api)",
            "inputSchema": {"type": "object", "properties": properties}}


MFP_LISTING = [mcp_tool(n) for n in (
    "fitness_log_food", "fitness_delete_food", "fitness_modify_food", "fitness_quick_add", "fitness_log_weight",
    "fitness_log_water", "fitness_log_note", "fitness_log_feel", "fitness_delete_exercise", "fitness_clear_food_pin",
    "fitness_list_food_pins", "fitness_set_goal", "fitness_get_goal", "fitness_draft_food", "fitness_bulk_export",
    "fitness_get_activity", "fitness_get_exercise", "fitness_get_exercise_entries", "fitness_get_note",
    "fitness_get_trends", "fitness_search_food",
)] + [mcp_tool("fitness_get_day", date={"type": "string"})]
HEVY_LISTING = [mcp_tool("hevy_get_account"), mcp_tool("hevy_list_workouts", limit={"type": "integer"}),
                mcp_tool("hevy_get_workout", workout_id={"type": "string"})]
EXPECTED = {"fitness_get_day", "fitness_get_activity", "fitness_get_exercise", "fitness_get_exercise_entries",
            "fitness_get_note", "fitness_get_trends", "fitness_search_food",
            "hevy_get_account", "hevy_list_workouts", "hevy_get_workout"}


@pytest.fixture
def listed(api):
    api.listings = {"mfp": MFP_LISTING, "hevy": HEVY_LISTING}
    return api


def test_the_allowlist_is_read_only():
    tools = live_tools.READ_TOOLS
    assert set(tools) == EXPECTED
    assert not [t for t in tools if any(w in t for w in WRITES)]
    assert {"fitness_set_goal", "fitness_quick_add", "fitness_log_food", "fitness_bulk_export"}.isdisjoint(tools)


async def test_the_chat_model_gets_the_allowed_live_tools_and_no_write_tool(coach, model, listed):
    model.script(reply("ok"))

    await coach.on_message("what did I eat on Tuesday?")

    tools = {t["name"]: t for t in model.requests[0].tools}
    live = {n for n in tools if n.startswith(("fitness_", "hevy_"))}
    assert live == EXPECTED
    assert not [n for n in tools if n.startswith(("fitness_", "hevy_")) and any(w in n for w in WRITES)]
    assert "fitness_set_goal" not in tools and "fitness_get_goal" not in tools
    # Schemas come from the api's listing.
    assert tools["fitness_get_day"]["input_schema"] == MFP_LISTING[-1]["inputSchema"]
    assert "get_context_notes" in tools  # the registered tools are still there


async def test_a_chat_lookup_goes_through_the_api_and_back_to_the_model(coach, model, listed, outbox):
    listed.tool_results["fitness_get_day"] = {"date": "2026-11-03", "diary": [{"name": "Oats, 80 g", "calories": 300}]}
    model.script(tool_call("fitness_get_day", date="2026-11-03"), reply("Oats for breakfast, 300 kcal."))

    await coach.on_message("what did I eat on Tuesday?")

    assert listed.read_calls() == [("mfp", "fitness_get_day", {"date": "2026-11-03"})]
    [result] = model.results(0)
    assert not result.is_error
    assert result.content == {"date": "2026-11-03", "diary": [{"name": "Oats, 80 g", "calories": 300}]}
    assert outbox.texts == ["Oats for breakfast, 300 kcal."]


async def test_a_write_the_model_names_anyway_is_refused_and_never_sent(coach, model, listed):
    model.script(tool_call("fitness_log_food", food="pizza"), reply("I can't log food."))

    await coach.on_message("log a pizza")

    assert model.results(0)[0].is_error
    assert listed.read_calls() == []


async def test_hevy_lookups_go_to_the_hevy_tools(coach, model, listed):
    listed.tool_results["hevy_get_workout"] = {"id": "w1", "exercises": []}
    model.script(tool_call("hevy_get_workout", workout_id="w1"), reply("ok"))

    await coach.on_message("what did I do on pull-ups?")

    assert listed.read_calls() == [("hevy", "hevy_get_workout", {"workout_id": "w1"})]


async def test_large_results_are_truncated_before_they_reach_the_model(coach, model, listed):
    listed.tool_results["fitness_get_trends"] = {"days": ["x" * 100] * 1000}
    model.script(tool_call("fitness_get_trends"), reply("ok"))

    await coach.on_message("trends?")

    content = model.results(0)[0].content
    assert content["truncated"] is True
    assert len(content["text"]) == live_tools.MAX_RESULT_CHARS


async def test_phase_start_gets_the_allowed_live_tools_and_no_write_tool(coach, model, listed):
    model.script(reply("Here is what I read from your history."))

    await coach.on_message("start reverse")

    names = {t["name"] for t in model.requests[-1].tools}
    assert {n for n in names if n.startswith(("fitness_", "hevy_"))} == EXPECTED
    assert not [n for n in names if n.startswith(("fitness_", "hevy_")) and any(w in n for w in WRITES)]
    assert {"record_setup_value", "start_phase"} <= names  # its own tools are still there
    assert "propose_change" not in names  # and only its own: not every registered tool


async def test_a_phase_start_lookup_goes_through_the_api(coach, model, listed):
    listed.tool_results["hevy_list_workouts"] = {"workouts": [{"id": "w1", "title": "Push"}]}
    model.script(reply("Here is what I read from your history."))
    await coach.on_message("start reverse")
    model.script(tool_call("hevy_list_workouts", limit=5), reply("Your last workout was Push."))

    await coach.on_message("what was my last workout?")

    assert listed.read_calls() == [("hevy", "hevy_list_workouts", {"limit": 5})]
    assert not model.results(len(model.requests) - 2)[0].is_error


async def test_tasks_without_tools_get_no_live_tools(coach, model, listed):
    model.script(reply("{}"))

    await coach.ask(["weekly-report"], tools=())

    assert model.requests[0].tools == ()
    assert listed.list_calls() == []


async def test_the_coach_starts_without_live_tools_when_listing_fails_and_retries_later(
        coach, model, listed, clock):
    listed.fail.add("list_tools")
    await coach.sync()  # start-up
    model.script(reply("ok"), reply("ok"), reply("ok"))

    await coach.on_message("hi")
    names = {t["name"] for t in model.requests[-1].tools}
    assert not [n for n in names if n.startswith(("fitness_", "hevy_"))]
    assert "get_context_notes" in names
    tries = len(listed.list_calls())

    listed.fail.clear()
    await coach.on_message("hi again")  # too soon to ask the api again
    assert len(listed.list_calls()) == tries

    clock.advance(seconds=live_tools.RETRY_AFTER.total_seconds())
    await coach.on_message("and now?")
    names = {t["name"] for t in model.requests[-1].tools}
    assert EXPECTED <= names


async def test_the_listing_is_fetched_once_and_cached(coach, model, listed):
    await coach.sync()
    model.script(reply("ok"), reply("ok"))
    await coach.on_message("one")
    await coach.on_message("two")

    assert sorted(s for s, in listed.list_calls()) == ["hevy", "mfp"]


@pytest.mark.parametrize("server,name", [("mfp", "fitness_set_goal"), ("mfp", "fitness_log_food"),
                                         ("mfp", "fitness_bulk_export"), ("hevy", "fitness_get_day")])
async def test_the_real_api_client_refuses_anything_but_an_allowed_read(server, name):
    from fa_coach.api_client import HttpApiClient

    client = HttpApiClient("http://api.invalid:8000", "http://api.invalid:8001")
    with pytest.raises(PermissionError):
        await client.read_tool(server, name, {})
