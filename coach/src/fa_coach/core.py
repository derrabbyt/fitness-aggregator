"""The Coach core: the one seam tests drive (spec, "Coach core").

Inputs: `sync`, `run_due_jobs`, `on_message`, `on_photo`, `on_button`, and
for the web page `view`, `refresh` and `command` (views.py).
Outputs: `Send` / `Edit` items in the outbox, plus state in the database.
Dependencies are injected: api client, model client, clock, outbox.
Model tasks run through `coach.ask(...)` (ask.py): the prompt layout, the
tool-call loop and schema-validated JSON output live there.

The core only dispatches; what each input does comes from the features
registered in `registry.py`. Handlers get the Coach itself and use
`coach.db`, `coach.api`, `coach.ask()`, `coach.skills`, `coach.say()`,
`coach.edit()`.
"""

import datetime
import logging
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from . import phases, views
from .ask import Answer, ask
from .db import Database
from .ports import ApiClient, Buttons, ChatTurn, Clock, Edit, ModelClient, Outbox, Send
from .registry import Registry, default_registry
from .skills import SkillsPackage

logger = logging.getLogger("fa-coach")

NO_CHAT_YET = "I can't chat yet. Commands: {commands}"


class Coach:
    def __init__(
        self,
        db_path: Path | str,
        *,
        api: ApiClient,
        model: ModelClient,
        clock: Clock,
        outbox: Outbox,
        skills: SkillsPackage | None = None,
        registry: Registry | None = None,
    ):
        self.db = Database(db_path)
        # The coach's state directory (state/coach): the database and stored files such as photos.
        self.state_dir = Path(db_path).parent
        self.api = api
        self.model = model
        self.clock = clock
        self.outbox = outbox
        self.skills = skills or SkillsPackage()
        self.registry = registry if registry is not None else default_registry()
        # The user's message being handled right now (None in jobs), so tools
        # such as add_context_note store the user's words unchanged.
        self.current_message: str | None = None

    # --- inputs --------------------------------------------------------------

    async def on_message(self, text: str, now: datetime.datetime | None = None) -> None:
        now = now or self.clock.now()
        text = text.strip()
        if text.startswith("/"):
            name, _, args = text[1:].partition(" ")
            command = self.registry.commands.get(name.split("@")[0].lower())
            if command is None:
                self.say(self.help_text())
                return
            await command.fn(self, args.strip(), now)
            return
        self.current_message = text
        try:
            for handler in self.registry.text_handlers:
                if await handler.fn(self, text, now):
                    return
        finally:
            self.current_message = None
        self.say(NO_CHAT_YET.format(commands=self._command_list()))

    async def on_photo(self, data: bytes, caption: str | None = None, now: datetime.datetime | None = None) -> None:
        now = now or self.clock.now()
        for handler in self.registry.photo_handlers:
            if await handler.fn(self, data, caption, now):
                return
        self.say("I don't take photos yet.")

    async def on_button(self, action: str, ref_id: str, now: datetime.datetime | None = None) -> None:
        now = now or self.clock.now()
        handler = self.registry.buttons.get(action)
        if handler is None:
            logger.warning("tap on unknown button %r (%s)", action, ref_id)
            return
        await handler(self, ref_id, now)

    async def sync(self, now: datetime.datetime | None = None) -> None:
        """Pull new records from the api into the database. One failing source
        doesn't stop the others."""
        now = now or self.clock.now()
        for syncer in self.registry.syncers:
            try:
                await syncer.fn(self, now)
            except Exception:
                logger.exception("sync %s failed", syncer.name)

    async def run_due_jobs(self, now: datetime.datetime | None = None) -> None:
        """Give every job a chance to run; each decides itself whether it is
        due (usually with `coach.db.once(...)`). One failing job doesn't stop
        the others."""
        now = now or self.clock.now()
        for job in self.registry.jobs:
            try:
                await job.fn(self, now)
            except Exception:
                logger.exception("job %s failed", job.name)

    # --- web page (views.py) ---------------------------------------------------

    def view(self, name: str, query: dict[str, str] | None = None,
             now: datetime.datetime | None = None) -> dict[str, Any]:
        """A read model from stored data, e.g. `view("home", {"day": "2026-11-10"})`.
        Raises `views.WebError` for an unknown view or a bad query."""
        return views.render(self, name, query or {}, now or self.clock.now())

    async def refresh(self, name: str, query: dict[str, str] | None = None,
                      now: datetime.datetime | None = None) -> dict[str, Any]:
        """Sync MFP and Hevy now, then return the read model."""
        now = now or self.clock.now()
        views.render(self, name, query or {}, now)  # refuse a bad request before syncing
        await self.sync(now)
        return views.render(self, name, query or {}, now)

    async def command(self, name: str, body: dict[str, Any] | None = None,
                      now: datetime.datetime | None = None) -> Any:
        """An edit from the web page (a registered web command)."""
        return await views.command(self, name, body or {}, now or self.clock.now())

    # --- model ---------------------------------------------------------------

    async def ask(
        self,
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
        """Run one model task to its end. `tools`: names of registered tools
        the model may call (None = all of them, () = none); code validates and
        executes each call once. `phase`: the phase whose skill goes in the
        cached prefix instead of the active one (phase start loads the target
        phase). With `output_schema`, `answer.data` is the schema-valid JSON
        object, else None with `answer.errors`. Raises
        `ModelError` when the model can't be reached."""
        return await ask(
            self,
            task_skills,
            input,
            tools=tools,
            output_schema=output_schema,
            decision=decision,
            history=history,
            phase=phase,
            now=now,
        )

    def active_phase_id(self) -> str | None:
        """The active phase; its skill joins the cached prefix. None before
        the user confirms a phase start."""
        phase = phases.active(self)
        return phase["phase_id"] if phase else None

    def state_snapshot(self, now: datetime.datetime) -> dict[str, Any]:
        """The short state snapshot every model task gets: the date, plus what
        the features' `registry.state` providers add."""
        state: dict[str, Any] = {
            "now": now.isoformat(timespec="minutes"),
            "today": now.date().isoformat(),
            "weekday": now.strftime("%A"),
        }
        for provider in self.registry.state_providers:
            state[provider.name] = provider.fn(self, now)
        return state

    # --- outputs -------------------------------------------------------------

    def say(self, text: str, buttons: Buttons = (), ref: str | None = None) -> None:
        self.outbox.put(Send(text, buttons, ref))

    def edit(self, ref: str, text: str, buttons: Buttons = ()) -> None:
        self.outbox.put(Edit(ref, text, buttons))

    def help_text(self) -> str:
        return f"Commands: {self._command_list()}"

    def _command_list(self) -> str:
        return ", ".join(f"/{name}" for name in sorted(self.registry.commands))
