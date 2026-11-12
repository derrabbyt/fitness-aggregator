"""What the Coach core talks to: its injected dependencies and its outbox.

The core holds no Telegram or network code. Real implementations live in
`api_client.py`, `model.py`, `clock.py` and `telegram_adapter.py`; tests use fakes
(`coach/tests/fakes.py`).
"""

import dataclasses
import datetime
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Goal:
    """An MFP nutrition goal: kcal and grams. The api's own spelling
    ({calories, protein, carbs, fat}) stays in api_client.py."""

    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float

    @classmethod
    def of(cls, values: Mapping[str, Any]) -> "Goal":
        """From a stored {kcal, protein_g, carbs_g, fat_g} dict (targets, proposals)."""
        return cls(**{f.name: values[f.name] for f in dataclasses.fields(cls)})

    def as_dict(self) -> dict[str, float]:
        return dataclasses.asdict(self)


class Clock(Protocol):
    def now(self) -> datetime.datetime:
        """Timezone-aware local time."""
        ...


class ApiClient(Protocol):
    """fa-api, the only way to MFP and Hevy: sync reads (REST) and
    `fitness_set_goal` (MCP, :8001). Methods are added by the tickets that
    need them; the core only ever calls what is declared here."""

    async def mfp_days(self, start: datetime.date, end: datetime.date) -> list[dict[str, Any]]:
        """`GET /api/sync/mfp`: one record per day, oldest first (README, Coach)."""
        ...

    async def hevy_sessions(self, start: datetime.date, end: datetime.date) -> list[dict[str, Any]]:
        """`GET /api/sync/hevy`: lifting sessions in the range, newest first (README, Coach)."""
        ...

    async def set_mfp_goal(self, goal: Goal) -> dict[str, Any]:
        """`fitness_set_goal`: send the MFP goal in exactly one request, never
        retried. Returns {"write": "sent" | "rejected" | "uncertain" |
        "not_sent" (refused before sending), "stored": the Goal the api read
        back after the write or None, "matches": whether that is the
        requested goal (None: not read back), "error": str | None}. Raises
        when the reply didn't arrive (the write may or may not have
        happened). Only `mfp_goal.set_once` calls this."""
        ...

    async def mfp_goal(self) -> Goal | None:
        """`fitness_get_goal`: the MFP goal in force today, None if MFP has
        none (or one without all four values)."""
        ...

    async def list_tools(self, server: str) -> list[dict[str, Any]]:
        """MCP `tools/list` of the api's "mfp" or "hevy" tools: [{name,
        description, inputSchema}]. Only `live_tools.py` calls this."""
        ...

    async def read_tool(self, server: str, name: str, args: dict[str, Any]) -> Any:
        """One live read for the model (`live_tools.READ_TOOLS` only; anything
        else is refused): the tool's JSON result, or its text."""
        ...


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
class Image:
    """An image the model sees in the user turn, after the input JSON, with a
    short `label` before it (e.g. "New set 2026-11-23, photo 1")."""

    label: str
    data: bytes
    media_type: str = "image/jpeg"


@dataclass(frozen=True)
class ModelRequest:
    """One model call. Layout (spec, "Claude"): a cached prefix
    (`prefix_skills` = coach-core + the active phase skill, plus `tools`),
    then the task skills, then a short `history`, then one user turn with the
    `state` snapshot and the `input` JSON (plus `images`, each after its
    label), then the tool loop so far (`steps`). With `output_schema` set, the final text must be one JSON
    object valid against that schema (`Coach.ask` validates it)."""

    prefix_skills: tuple[str, ...]
    task_skills: tuple[str, ...]
    input: Any = None
    state: dict[str, Any] = field(default_factory=dict)
    tools: tuple[dict[str, Any], ...] = ()  # Anthropic tool definitions
    history: tuple[ChatTurn, ...] = ()
    steps: tuple[Step, ...] = ()
    output_schema: str | None = None  # schema name, e.g. "weekly_verdict"
    images: tuple[Image, ...] = ()  # e.g. the photo review's photo sets
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
