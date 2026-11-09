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


@dataclass
class ModelRequest:
    """One model call. The prompt layout is fixed by the spec: a cached prefix
    (coach-core + active phase skill + tool definitions), then the task skill,
    then a short state snapshot and the input JSON."""

    task_skill: str
    input: Any = None
    phase_skill: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    output_schema: str | None = None  # schema file name; the reply's `data` is validated against it
    decision: bool = False  # True: COACH_DECISION_MODEL, else COACH_MODEL


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class ModelReply:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    data: dict[str, Any] | None = None  # schema-validated JSON output


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
