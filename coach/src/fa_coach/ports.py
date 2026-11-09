"""What the Coach core talks to: its injected dependencies and its outbox.

The core holds no Telegram or network code. Real implementations live in
`api_client.py`, `model.py`, `clock.py` and `telegram_adapter.py`; tests use fakes
(`coach/tests/fakes.py`).
"""

import datetime
from dataclasses import dataclass, field
from typing import Any, Protocol


class Clock(Protocol):
    def now(self) -> datetime.datetime:
        """Timezone-aware local time."""
        ...


class ApiClient(Protocol):
    """fa-api, the only way to MFP and Hevy: sync reads (REST) and
    `fitness_set_goal` (MCP, :8001). Methods are added by the tickets that
    need them; the core only ever calls what is declared here."""


@dataclass(frozen=True)
class ToolCall:
    """The model asks code to run a registered tool."""

    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """What code sends back for one `ToolCall` (`content` is JSON-able)."""

    call_id: str
    content: Any
    is_error: bool = False


@dataclass(frozen=True)
class ModelReply:
    """One model turn: final text, or tool calls for code to run first.

    `raw` is the provider's own content (e.g. Anthropic blocks, including
    thinking); the model client sends it back unchanged when the tool loop
    continues. Fakes leave it None."""

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    stop_reason: str = "end_turn"
    raw: Any = None


# An assistant turn and the tool results code produced for it.
Step = tuple[ModelReply, tuple[ToolResult, ...]]


@dataclass(frozen=True)
class ChatTurn:
    role: str  # "user" | "assistant"
    text: str


@dataclass(frozen=True)
class ModelRequest:
    """One model call. Layout (spec, "Claude"): a cached prefix
    (`prefix_skills` = coach-core + the active phase skill, plus `tools`),
    then the task skills, then a short `history`, then one user turn with the
    `state` snapshot and the `input` JSON, then the tool loop so far
    (`steps`). With `output_schema` set, the final text must be one JSON
    object valid against that schema (`Coach.ask` validates it)."""

    prefix_skills: tuple[str, ...]
    task_skills: tuple[str, ...]
    input: Any = None
    state: dict[str, Any] = field(default_factory=dict)
    tools: tuple[dict[str, Any], ...] = ()  # Anthropic tool definitions
    history: tuple[ChatTurn, ...] = ()
    steps: tuple[Step, ...] = ()
    output_schema: str | None = None  # schema name, e.g. "weekly_verdict"
    decision: bool = False  # True: COACH_DECISION_MODEL, else COACH_MODEL


class ModelError(Exception):
    """The model could not be reached or gave no usable answer. The message
    is short and safe to show to the user."""


class ModelClient(Protocol):
    async def run(self, request: ModelRequest) -> ModelReply: ...


# --- outbox ------------------------------------------------------------------

CALLBACK_LIMIT = 64  # Telegram's callback_data limit in bytes


@dataclass(frozen=True)
class Button:
    """Tapping it calls `Coach.on_button(action, ref_id)`."""

    label: str
    action: str
    ref_id: str

    def __post_init__(self) -> None:
        if ":" in self.action or len(self.callback_data.encode()) > CALLBACK_LIMIT:
            raise ValueError(f"button {self.action!r}/{self.ref_id!r} can't be encoded as callback data")

    @property
    def callback_data(self) -> str:
        return f"{self.action}:{self.ref_id}"


Buttons = tuple[tuple[Button, ...], ...]  # rows of buttons


@dataclass(frozen=True)
class Send:
    """A new message to the user. `ref` names it (e.g. "proposal:abc") so a
    later `Edit` can replace its text and buttons."""

    text: str
    buttons: Buttons = ()
    ref: str | None = None


@dataclass(frozen=True)
class Edit:
    """Replace the text and buttons of the message sent with `ref` (no
    buttons = remove them). Sent as a new message if that one is unknown."""

    ref: str
    text: str
    buttons: Buttons = ()


Outgoing = Send | Edit


class Outbox(Protocol):
    def put(self, item: Outgoing) -> None: ...
