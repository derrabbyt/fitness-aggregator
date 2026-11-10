"""The real model client turns a ModelRequest into one Anthropic Messages call:
cached prefix (tools, coach-core, phase skill), then the task skills, then a
short history and one user turn with the state snapshot and input; the tool
loop goes back as the model's own content plus tool results. No network: the
SDK client is a recording fake."""

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from fa_coach.config import Settings
from fa_coach.model import AnthropicModel
from fa_coach.ports import ChatTurn, ModelError, ModelReply, ModelRequest, ToolCall, ToolResult
from fa_coach.skills import SkillsPackage

CACHED = {"type": "ephemeral"}
TOOL = {"name": "get_coach_profile", "description": "Profile", "input_schema": {"type": "object"}}


def block(type, **fields):
    return SimpleNamespace(type=type, **fields)


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **params):
        self.calls.append(params)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def response(*content, stop_reason="end_turn"):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(content=list(content), stop_reason=stop_reason, usage=usage)


def make_model(*responses):
    messages = FakeMessages(responses)
    sdk = SimpleNamespace(messages=messages)
    return AnthropicModel(sdk, SkillsPackage(), model="claude-sonnet-5-5", decision_model="claude-opus-5-5"), messages


def request(**overrides):
    fields = dict(
        prefix_skills=("coach-core", "phase-reverse-bulk"),
        task_skills=("coach-chat", "context-log"),
        input={"message": "sick since Tuesday"},
        state={"today": "2026-11-09"},
        tools=(TOOL,),
    )
    fields.update(overrides)
    return ModelRequest(**fields)


async def test_prompt_layout_puts_the_stable_prefix_first_and_caches_it():
    model, sdk = make_model(response(block("text", text="Noted.")))
    skills = SkillsPackage()

    reply = await model.run(request(history=(ChatTurn("user", "hi"), ChatTurn("assistant", "hello"))))

    [params] = sdk.calls
    assert params["model"] == "claude-sonnet-5-5"
    assert params["tools"] == [TOOL]
    system = params["system"]
    assert [b["text"] for b in system] == [
        skills.skill("coach-core"),
        skills.skill("phase-reverse-bulk"),
        skills.skill("coach-chat") + "\n\n" + skills.skill("context-log"),
    ]
    # One breakpoint after the prefix (tools + core + phase), one after the task skills.
    assert [b.get("cache_control") for b in system] == [None, CACHED, CACHED]
    messages = params["messages"]
    assert messages[:2] == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    last = messages[2]
    assert last["role"] == "user"
    text = last["content"][0]["text"]
    assert json.loads(text.split("State:\n", 1)[1].split("\n\nInput:\n")[0]) == {"today": "2026-11-09"}
    assert json.loads(text.split("Input:\n", 1)[1]) == {"message": "sick since Tuesday"}
    assert reply == ModelReply(text="Noted.", raw=[block("text", text="Noted.")])


async def test_the_decision_model_is_used_for_decisions():
    model, sdk = make_model(response(block("text", text="{}")))

    await model.run(request(decision=True, tools=()))

    assert sdk.calls[0]["model"] == "claude-opus-5-5"
    assert "tools" not in sdk.calls[0]


async def test_tool_calls_come_back_and_the_loop_is_sent_as_content_plus_results():
    thinking = block("thinking", thinking="", signature="sig")
    use = block("tool_use", id="toolu_1", name="get_coach_profile", input={})
    model, sdk = make_model(response(thinking, use, stop_reason="tool_use"), response(block("text", text="You prefer kg.")))

    first = await model.run(request())
    assert first.tool_calls == (ToolCall("toolu_1", "get_coach_profile", {}),)
    assert first.stop_reason == "tool_use"

    await model.run(request(steps=((first, (ToolResult("toolu_1", {"profile": {"units": "kg"}}),)),)))

    messages = sdk.calls[1]["messages"]
    assert messages[-2] == {"role": "assistant", "content": [thinking, use]}  # unchanged, thinking included
    assert messages[-1] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": json.dumps({"profile": {"units": "kg"}}),
                "is_error": False,
                "cache_control": CACHED,  # the loop so far is cached for the next turn
            }
        ],
    }


async def test_an_output_schema_is_given_with_the_task():
    model, sdk = make_model(response(block("text", text="{}")))

    await model.run(request(output_schema="context_note", tools=()))

    task = sdk.calls[0]["system"][-1]["text"]
    assert "one JSON object" in task
    assert '"$id": "context_note.schema.json"' in task


async def test_a_refusal_is_reported_as_such():
    model, _ = make_model(response(stop_reason="refusal"))

    reply = await model.run(request())

    assert reply.stop_reason == "refusal"
    assert reply.text == ""


@pytest.mark.parametrize(
    "error, shown",
    [
        (anthropic.APIConnectionError(request=httpx.Request("POST", "https://x")), "connection failed"),
        (
            anthropic.RateLimitError(
                "slow down", response=httpx.Response(429, request=httpx.Request("POST", "https://x")), body=None
            ),
            "HTTP 429",
        ),
    ],
)
async def test_api_failures_become_short_model_errors(error, shown):
    model, _ = make_model(error)

    with pytest.raises(ModelError, match=shown):
        await model.run(request())


def test_settings_prefer_the_coachs_own_endpoint_and_key():
    base = {"COACH_TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_ALLOWED_USER_ID": "1"}
    shared = Settings.from_env({**base, "ANTHROPIC_API_KEY": "shared", "ANTHROPIC_BASE_URL": "http://proxy"})
    own = Settings.from_env(
        {
            **base,
            "ANTHROPIC_API_KEY": "shared",
            "COACH_ANTHROPIC_API_KEY": "own",
            "COACH_ANTHROPIC_BASE_URL": "http://coach-proxy",
            "COACH_MODEL": "claude-haiku-5-5",
        }
    )

    assert (shared.anthropic_api_key, shared.anthropic_base_url, shared.model) == ("shared", "http://proxy", "claude-sonnet-5-5")
    assert (own.anthropic_api_key, own.anthropic_base_url, own.model) == ("own", "http://coach-proxy", "claude-haiku-5-5")
