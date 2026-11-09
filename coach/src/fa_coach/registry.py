"""Where features plug into the Coach core.

Each feature is one module in `fa_coach/features/`, found automatically, that
registers its handlers on the shared `registry`:

    from ..registry import registry

    @registry.command("profile", "Show your coach profile")
    async def profile(coach, args, now): ...

    @registry.text(order=50)          # free text; return True if handled
    @registry.button("approve")       # button taps: (coach, ref_id, now)
    @registry.photo()                 # photos: (coach, data, caption, now) -> bool
    @registry.job("evening")          # every scheduler tick: (coach, now); decides itself if due
    @registry.syncer("mfp")           # Coach.sync: (coach, now)
    @registry.tool("add_context_note", "description", {input JSON schema})
                                      # model tools: (coach, args, now) -> JSON-able result;
                                      # args are validated against the schema first;
                                      # raise ask.ToolError to refuse with a message
    @registry.state("profile")        # adds a key to the state snapshot of every model
                                      # task: (coach, now) -> small JSON-able value

Database tables come from `fa_coach/migrations/NN_<name>.sql` (NN = ticket
number), so adding a feature means adding files, not editing shared ones.
Names must be unique; a clash fails at import.
"""

import datetime
import importlib
import pkgutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core import Coach

Now = datetime.datetime
CommandFn = Callable[["Coach", str, Now], Awaitable[None]]
TextFn = Callable[["Coach", str, Now], Awaitable[bool]]
ButtonFn = Callable[["Coach", str, Now], Awaitable[None]]
PhotoFn = Callable[["Coach", bytes, str | None, Now], Awaitable[bool]]
JobFn = Callable[["Coach", Now], Awaitable[None]]
ToolFn = Callable[["Coach", dict[str, Any], Now], Awaitable[Any]]
StateFn = Callable[["Coach", Now], Any]


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    fn: CommandFn


@dataclass(frozen=True)
class Ordered:
    """A text/photo handler, job, syncer or state provider; run in (order,
    name) order."""

    name: str
    order: int
    fn: Callable[..., Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: ToolFn

    def definition(self) -> dict[str, Any]:
        """Anthropic tool definition."""
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


class Registry:
    def __init__(self) -> None:
        self.commands: dict[str, Command] = {}
        self.buttons: dict[str, ButtonFn] = {}
        self.tools: dict[str, Tool] = {}
        self._text: dict[str, Ordered] = {}
        self._photo: dict[str, Ordered] = {}
        self._jobs: dict[str, Ordered] = {}
        self._syncers: dict[str, Ordered] = {}
        self._state: dict[str, Ordered] = {}

    # --- registration ------------------------------------------------------

    def command(self, name: str, help: str) -> Callable[[CommandFn], CommandFn]:
        def add(fn: CommandFn) -> CommandFn:
            _unique(self.commands, name, "command")
            self.commands[name] = Command(name, help, fn)
            return fn

        return add

    def button(self, action: str) -> Callable[[ButtonFn], ButtonFn]:
        def add(fn: ButtonFn) -> ButtonFn:
            _unique(self.buttons, action, "button")
            self.buttons[action] = fn
            return fn

        return add

    def tool(self, name: str, description: str, input_schema: dict[str, Any]) -> Callable[[ToolFn], ToolFn]:
        def add(fn: ToolFn) -> ToolFn:
            _unique(self.tools, name, "tool")
            self.tools[name] = Tool(name, description, input_schema, fn)
            return fn

        return add

    def text(self, order: int = 100) -> Callable[[TextFn], TextFn]:
        return self._ordered(self._text, "text handler", order)

    def photo(self, order: int = 100) -> Callable[[PhotoFn], PhotoFn]:
        return self._ordered(self._photo, "photo handler", order)

    def job(self, name: str, order: int = 100) -> Callable[[JobFn], JobFn]:
        return self._ordered(self._jobs, "job", order, name)

    def syncer(self, name: str, order: int = 100) -> Callable[[JobFn], JobFn]:
        return self._ordered(self._syncers, "syncer", order, name)

    def state(self, name: str, order: int = 100) -> Callable[[StateFn], StateFn]:
        return self._ordered(self._state, "state provider", order, name)

    def _ordered(self, table: dict[str, Ordered], kind: str, order: int, name: str | None = None):
        def add(fn):
            key = name or f"{fn.__module__}.{fn.__qualname__}"
            _unique(table, key, kind)
            table[key] = Ordered(key, order, fn)
            return fn

        return add

    # --- lookup --------------------------------------------------------------

    @property
    def text_handlers(self) -> list[Ordered]:
        return _sorted(self._text)

    @property
    def photo_handlers(self) -> list[Ordered]:
        return _sorted(self._photo)

    @property
    def jobs(self) -> list[Ordered]:
        return _sorted(self._jobs)

    @property
    def syncers(self) -> list[Ordered]:
        return _sorted(self._syncers)

    @property
    def state_providers(self) -> list[Ordered]:
        return _sorted(self._state)


def _unique(table: dict, name: str, kind: str) -> None:
    if name in table:
        raise ValueError(f"{kind} {name!r} is registered twice")


def _sorted(table: dict[str, Ordered]) -> list[Ordered]:
    return sorted(table.values(), key=lambda o: (o.order, o.name))


registry = Registry()
_loaded = False


def default_registry() -> Registry:
    """The shared registry with every module in `fa_coach.features` imported."""
    global _loaded
    if not _loaded:
        from . import features

        for module in pkgutil.iter_modules(features.__path__):
            importlib.import_module(f"{features.__name__}.{module.name}")
        _loaded = True
    return registry
