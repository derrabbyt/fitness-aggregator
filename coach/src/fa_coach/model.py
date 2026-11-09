"""The real model client: the Anthropic SDK (ADR 0003), one Messages call per
model turn. The tool loop itself runs in `ask.py`; this module only maps a
`ModelRequest` onto the API and the response back onto a `ModelReply`.

Prompt layout (render order tools → system → messages), so the stable part
is cached across calls:

- tools (sorted by `ask.py`), then system blocks coach-core and the active
  phase skill → cache breakpoint 1 (the prefix);
- the task skills (and the output schema, if any) → cache breakpoint 2;
- a short chat history, then one user turn: state snapshot + input JSON;
- the tool loop so far: the model's own content (thinking included, sent
  back unchanged) and code's tool results → breakpoint 3 on the last result.

Endpoint, key and models come from Settings (COACH_ANTHROPIC_* falling back
to ANTHROPIC_*, COACH_MODEL, COACH_DECISION_MODEL).
"""

import json
import logging
import re
from typing import Any

import anthropic

from .config import Settings
from .ports import ModelClient, ModelError, ModelReply, ModelRequest, ToolCall
from .skills import SkillsPackage

logger = logging.getLogger("fa-coach")

MAX_TOKENS = 16000
CACHED = {"type": "ephemeral"}
JSON_ANSWER = (
    "Answer with one JSON object only (no prose, no code fence), valid against the JSON schema "
    "`{name}` below. Schemas it refers to by file name follow it."
)


class AnthropicModel:
    def __init__(self, client: Any, skills: SkillsPackage, *, model: str, decision_model: str):
        self.client = client  # anthropic.AsyncAnthropic, or a fake in tests
        self.skills = skills
        self.model = model
        self.decision_model = decision_model

    async def run(self, request: ModelRequest) -> ModelReply:
        try:
            response = await self.client.messages.create(**self.params(request))
        except anthropic.APIStatusError as exc:
            raise ModelError(f"HTTP {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise ModelError("connection failed") from exc
        except anthropic.AnthropicError as exc:
            raise ModelError(type(exc).__name__) from exc
        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info(
                "model %s: in %s (cache read %s, write %s), out %s",
                request.task_skills,
                usage.input_tokens,
                getattr(usage, "cache_read_input_tokens", None),
                getattr(usage, "cache_creation_input_tokens", None),
                usage.output_tokens,
            )
        return _reply(response)

    def params(self, request: ModelRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.decision_model if request.decision else self.model,
            "max_tokens": MAX_TOKENS,
            "system": self._system(request),
            "messages": self._messages(request),
        }
        if request.tools:
            params["tools"] = list(request.tools)
        return params

    def _system(self, request: ModelRequest) -> list[dict[str, Any]]:
        prefix = [{"type": "text", "text": self.skills.skill(name)} for name in request.prefix_skills]
        prefix[-1]["cache_control"] = CACHED
        task = "\n\n".join(self.skills.skill(name) for name in request.task_skills)
        if request.output_schema:
            task += "\n\n" + self._schema_text(request.output_schema)
        return prefix + [{"type": "text", "text": task, "cache_control": CACHED}]

    def _schema_text(self, name: str) -> str:
        parts = [JSON_ANSWER.format(name=name)]
        for schema_name in _with_references(self.skills, name):
            parts.append(f"{schema_name}.schema.json:\n{json.dumps(self.skills.schema(schema_name), indent=1)}")
        return "\n\n".join(parts)

    def _messages(self, request: ModelRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": t.role, "content": t.text} for t in request.history]
        turn = f"State:\n{_json(request.state)}\n\nInput:\n{_json(request.input)}"
        messages.append({"role": "user", "content": [{"type": "text", "text": turn}]})
        for reply, results in request.steps:
            messages.append({"role": "assistant", "content": reply.raw if reply.raw is not None else _content(reply)})
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r.call_id,
                            "content": _json(r.content),
                            "is_error": r.is_error,
                        }
                        for r in results
                    ],
                }
            )
        if request.steps:
            messages[-1]["content"][-1]["cache_control"] = CACHED
        return messages


def _reply(response: Any) -> ModelReply:
    content = list(response.content)
    text = "\n".join(b.text for b in content if b.type == "text")
    calls = tuple(ToolCall(b.id, b.name, dict(b.input or {})) for b in content if b.type == "tool_use")
    return ModelReply(text=text.strip(), tool_calls=calls, stop_reason=response.stop_reason or "end_turn", raw=content)


def _content(reply: ModelReply) -> list[dict[str, Any]]:
    """Assistant content for a reply without provider content (fakes)."""
    blocks: list[dict[str, Any]] = [{"type": "text", "text": reply.text}] if reply.text else []
    blocks += [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.args} for c in reply.tool_calls]
    return blocks


def _json(value: Any) -> str:
    # Sorted keys: the same data gives the same bytes (cache-friendly).
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _with_references(skills: SkillsPackage, name: str) -> list[str]:
    """The schema and every schema file it references, transitively."""
    seen: list[str] = []
    todo = [name]
    while todo:
        current = todo.pop(0)
        if current in seen:
            continue
        seen.append(current)
        text = json.dumps(skills.schema(current))
        todo += re.findall(r'"\$ref": "([a-z_]+)\.schema\.json', text)
    return seen


class NoModel:
    """Stands in when the SDK client can't be built; every call fails with a
    short reason."""

    def __init__(self, reason: str):
        self.reason = reason

    async def run(self, request: ModelRequest) -> ModelReply:
        raise ModelError(self.reason)


def build_model_client(settings: Settings) -> ModelClient:
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url)
    except anthropic.AnthropicError as exc:
        logger.error("no model client: %s", type(exc).__name__)
        return NoModel("no model client configured")
    return AnthropicModel(client, SkillsPackage(), model=settings.model, decision_model=settings.decision_model)
