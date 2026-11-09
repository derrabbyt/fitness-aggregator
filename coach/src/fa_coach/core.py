"""The Coach core: the one seam tests drive (spec, "Coach core").

Inputs: `sync`, `run_due_jobs`, `on_message`, `on_photo`, `on_button`.
Outputs: `Send` / `Edit` items in the outbox, plus state in the database.
Dependencies are injected: api client, model client, clock, outbox.

The core only dispatches; what each input does comes from the features
registered in `registry.py`. Handlers get the Coach itself and use
`coach.db`, `coach.api`, `coach.model`, `coach.skills`, `coach.say()`,
`coach.edit()`.
"""

import datetime
import logging
from pathlib import Path

from .db import Database
from .ports import ApiClient, Buttons, Clock, Edit, ModelClient, Outbox, Send
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
        self.api = api
        self.model = model
        self.clock = clock
        self.outbox = outbox
        self.skills = skills or SkillsPackage()
        self.registry = registry if registry is not None else default_registry()

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
        for handler in self.registry.text_handlers:
            if await handler.fn(self, text, now):
                return
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

    # --- outputs -------------------------------------------------------------

    def say(self, text: str, buttons: Buttons = (), ref: str | None = None) -> None:
        self.outbox.put(Send(text, buttons, ref))

    def edit(self, ref: str, text: str, buttons: Buttons = ()) -> None:
        self.outbox.put(Edit(ref, text, buttons))

    def help_text(self) -> str:
        return f"Commands: {self._command_list()}"

    def _command_list(self) -> str:
        return ", ".join(f"/{name}" for name in sorted(self.registry.commands))
