"""Thin Telegram adapter and scheduler loop around the Coach core.

Updates from the one allowed user become `on_message` / `on_photo` /
`on_button` calls; everyone else is ignored. A scheduler loop calls `sync`
and `run_due_jobs`. After every core call the outbox is sent. One core call
runs at a time. Only one process may poll a bot token. The web page's HTTP
API (web_adapter.py) runs in the same event loop; its refreshes and edits go
through `web_call`.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from . import web_adapter
from .core import Coach
from .ports import Buttons, Edit, Outgoing, Send

logger = logging.getLogger("fa-coach")

TICK_SECONDS = 60  # how often run_due_jobs runs
SYNC_EVERY_SECONDS = 4 * 3600  # sync on start, then several times a day
TELEGRAM_LIMIT = 4000


class QueueOutbox:
    """Collects outgoing items until the adapter sends them."""

    def __init__(self) -> None:
        self.items: list[Outgoing] = []

    def put(self, item: Outgoing) -> None:
        self.items.append(item)

    def drain(self) -> list[Outgoing]:
        items, self.items = self.items, []
        return items


class TelegramAdapter:
    def __init__(self, coach: Coach, outbox: QueueOutbox, allowed_user_id: int):
        self.coach = coach
        self.outbox = outbox
        self.allowed = allowed_user_id
        self.lock = asyncio.Lock()
        self.bot = None  # set once the application is up

    # --- updates -------------------------------------------------------------

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if not self._from_allowed(update) or msg is None or not msg.text:
            return
        await self._run(context.bot, lambda: self.coach.on_message(msg.text))

    async def on_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if not self._from_allowed(update) or msg is None or not msg.photo:
            return
        file = await msg.photo[-1].get_file()
        data = bytes(await file.download_as_bytearray())
        await self._run(context.bot, lambda: self.coach.on_photo(data, msg.caption))

    async def on_tap(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or query.from_user is None or query.from_user.id != self.allowed or not query.data:
            return
        await query.answer()
        action, _, ref_id = query.data.partition(":")
        await self._run(context.bot, lambda: self.coach.on_button(action, ref_id))

    def _from_allowed(self, update: Update) -> bool:
        return update.effective_user is not None and update.effective_user.id == self.allowed

    # --- scheduler -------------------------------------------------------------

    async def scheduler(self, bot) -> None:
        loop = asyncio.get_running_loop()
        next_sync = 0.0
        while True:
            if loop.time() >= next_sync:
                next_sync = loop.time() + SYNC_EVERY_SECONDS
                await self._run(bot, self.coach.sync)
            await self._run(bot, self.coach.run_due_jobs)
            await asyncio.sleep(TICK_SECONDS)

    # --- core calls and delivery ---------------------------------------------

    async def web_call(self, call: Callable[[], Awaitable[Any]]) -> Any:
        """A core call from the web page: under the same lock, its result
        returned (errors raised to the HTTP adapter), the outbox sent."""
        async with self.lock:
            try:
                return await call()
            finally:
                for item in self.outbox.drain():
                    try:
                        await self._deliver(self.bot, item)
                    except Exception:  # noqa: BLE001
                        logger.exception("sending to Telegram failed")

    async def _run(self, bot, call: Callable[[], Awaitable[None]]) -> None:
        async with self.lock:
            try:
                await call()
            except Exception as exc:  # noqa: BLE001
                logger.exception("coach call failed")
                self.coach.say(f"⚠️ That failed ({type(exc).__name__}). Details are in the coach's log.")
            for item in self.outbox.drain():
                try:
                    await self._deliver(bot, item)
                except Exception:  # noqa: BLE001
                    logger.exception("sending to Telegram failed")

    async def _deliver(self, bot, item: Outgoing) -> None:
        chat_id = self.allowed  # private chat: chat id == user id
        if isinstance(item, Edit):
            row = self.coach.db.one("SELECT chat_id, message_id FROM sent_messages WHERE ref = ?", (item.ref,))
            if row is not None:
                await bot.edit_message_text(
                    item.text[:TELEGRAM_LIMIT],
                    chat_id=row["chat_id"],
                    message_id=row["message_id"],
                    reply_markup=_keyboard(item.buttons),
                )
                return
            item = Send(item.text, item.buttons, item.ref)
        chunks = _chunks(item.text)
        sent = None
        for i, chunk in enumerate(chunks):
            last = i == len(chunks) - 1
            sent = await bot.send_message(chat_id, chunk, reply_markup=_keyboard(item.buttons) if last else None)
        if item.ref and sent is not None:
            self.coach.db.execute(
                "INSERT OR REPLACE INTO sent_messages (ref, chat_id, message_id, sent_at) VALUES (?, ?, ?, ?)",
                (item.ref, chat_id, sent.message_id, self.coach.clock.now().isoformat()),
            )


def _keyboard(buttons: Buttons) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(b.label, callback_data=b.callback_data) for b in row] for row in buttons]
    )


def _chunks(text: str) -> list[str]:
    text = text.strip() or "…"
    chunks = []
    while len(text) > TELEGRAM_LIMIT:
        cut = text.rfind("\n", 0, TELEGRAM_LIMIT)
        cut = cut if cut > 0 else TELEGRAM_LIMIT
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    chunks.append(text)
    return chunks


def run(coach: Coach, outbox: QueueOutbox, token: str, allowed_user_id: int, *, web_host: str = "0.0.0.0",
        web_port: int = 8002) -> None:
    adapter = TelegramAdapter(coach, outbox, allowed_user_id)
    tasks: list[asyncio.Task] = []

    async def post_init(app: Application) -> None:
        await app.bot.set_my_commands(
            [BotCommand(c.name, c.help) for c in sorted(coach.registry.commands.values(), key=lambda c: c.name)]
        )
        adapter.bot = app.bot
        tasks.append(asyncio.create_task(adapter.scheduler(app.bot)))
        tasks.append(asyncio.create_task(web_adapter.serve(coach, adapter.web_call, web_host, web_port)))

    async def post_shutdown(app: Application) -> None:
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("telegram error: %s", context.error)

    app = Application.builder().token(token).post_init(post_init).post_shutdown(post_shutdown).build()
    only_you = filters.User(allowed_user_id)
    app.add_handler(MessageHandler(only_you & filters.TEXT, adapter.on_text))
    app.add_handler(MessageHandler(only_you & filters.PHOTO, adapter.on_photo))
    app.add_handler(CallbackQueryHandler(adapter.on_tap))
    app.add_error_handler(on_error)
    logger.info("fa-coach polling")
    app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=False)
