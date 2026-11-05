"""Telegram bot (`fa-bot`): long polling, one allowed user, voice via whisper.cpp.

Environment (see .env.example): TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_ID,
BOT_MODEL (e.g. anthropic:claude-sonnet-5-5) plus that provider's API key,
FA_TOOLS_URL (the api's MCP endpoint, default http://127.0.0.1:8001).
Only one process may poll a bot token.
"""

import asyncio
import contextlib
import datetime
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path

from pydantic_ai import BinaryContent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.usage import UsageLimits
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import NetworkError
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from .config import STATE, load_env
from .agent import Deps, DraftCache, build_agent
from .cards import card_text, result_text, status_text
from .changes import ChangeStore, _short, execute
from .history import History

logger = logging.getLogger("fa-bot")
BOT_STATE = STATE / "bot"
REQUEST_LIMIT = 15
WHISPER_CLI = os.environ.get("WHISPER_CLI", "whisper-cli")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "/usr/local/share/whisper-cpp/models/ggml-small.bin")
TELEGRAM_LIMIT = 4000


class Bot:
    def __init__(self, env: dict[str, str]):
        BOT_STATE.mkdir(parents=True, exist_ok=True)
        self.allowed = int(env["TELEGRAM_ALLOWED_USER_ID"])
        self.model = env.get("BOT_MODEL") or "anthropic:claude-sonnet-5-5"
        self.agent, self.mfp = build_agent(self.model, env.get("FA_TOOLS_URL") or "http://127.0.0.1:8001")
        self.changes = ChangeStore(BOT_STATE / "bot.db")
        self.history = History(BOT_STATE / "bot.db")
        self.drafts = DraftCache()
        self.lock = asyncio.Lock()  # one model run at a time
        self.usage_log = BOT_STATE / "usage.jsonl"

    async def call_mfp(self, name: str, args: dict):
        """Direct mfp tool call by the bot's own code (card execution, reads)."""
        return await self.mfp.direct_call_tool(name, args)

    # --- incoming messages -------------------------------------------------

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None or update.effective_user is None or update.effective_user.id != self.allowed:
            return  # silently ignore everyone else
        chat_id = msg.chat_id
        prompt: list = []
        heard = None
        try:
            if msg.voice or msg.audio:
                media = msg.voice or msg.audio
                file = await media.get_file()
                heard = await transcribe(bytes(await file.download_as_bytearray()))
                if not heard:
                    await msg.reply_text("🎤 I couldn't understand that voice note.")
                    return
                prompt.append(f"[voice note, transcribed] {heard}")
            if msg.photo:
                file = await msg.photo[-1].get_file()
                prompt.append(BinaryContent(data=bytes(await file.download_as_bytearray()), media_type="image/jpeg"))
            text = msg.text or msg.caption
            if text:
                prompt.append(text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("reading message failed")
            await msg.reply_text(f"⚠️ {_short(exc)}")
            return
        if not prompt:
            return

        async with self.lock, typing(context, chat_id):
            deps = Deps(chat_id=chat_id, call=self.call_mfp, drafts=self.drafts)
            started = time.time()
            try:
                result = await self.agent.run(
                    prompt,
                    deps=deps,
                    message_history=self.history.load(chat_id),
                    usage_limits=UsageLimits(request_limit=REQUEST_LIMIT),
                )
            except UsageLimitExceeded:
                await msg.reply_text("⚠️ Stopped: that took too many steps. Try asking more specifically.")
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("agent run failed")
                await msg.reply_text(f"⚠️ {_short(exc)}")
                return
            self.history.save(chat_id, result.new_messages())
            self._log_usage(chat_id, result, time.time() - started)

        reply = result.output.strip()
        if heard:
            reply = f"🎤 „{heard}“\n\n{reply}".strip()
        for chunk in _chunks(reply):
            await msg.reply_text(chunk)
        if deps.card:
            await self._send_card(context, deps.card)

    async def _send_card(self, context: ContextTypes.DEFAULT_TYPE, change) -> None:
        for old in self.changes.add(change):
            if old.message_id:
                with contextlib.suppress(Exception):
                    await context.bot.edit_message_text(
                        status_text(old, "superseded"), chat_id=old.chat_id, message_id=old.message_id,
                        parse_mode=ParseMode.HTML,
                    )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("✅", callback_data=f"ok:{change.id}"), InlineKeyboardButton("❌", callback_data=f"no:{change.id}")]]
        )
        sent = await context.bot.send_message(
            change.chat_id, card_text(change), parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
        self.changes.set_message(change, sent.message_id)
        self.history.note(change.chat_id, f"Card {change.id} shown, waiting for the user's tap: {_plain(card_text(change))}")

    # --- button taps -------------------------------------------------------

    async def on_tap(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or query.from_user.id != self.allowed or not query.data or ":" not in query.data:
            return
        action, change_id = query.data.split(":", 1)
        chat_id = query.message.chat.id if query.message else None
        await query.answer()

        if action == "no":
            status, change = self.changes.cancel(change_id, chat_id)
            if change:
                await query.edit_message_text(status_text(change, "cancelled" if status == "ok" else status), parse_mode=ParseMode.HTML)
                if status == "ok":
                    self.history.note(chat_id, f"The user cancelled card {change.id}; nothing was written.")
            return

        status, change = self.changes.claim(change_id, chat_id)
        if status != "ok":
            if change and status in ("expired", "cancelled", "superseded"):
                await query.edit_message_text(status_text(change, status), parse_mode=ParseMode.HTML)
            return  # running/done: the first tap already handles it
        await query.edit_message_text(card_text(change) + "\n⏳ …", parse_mode=ParseMode.HTML)
        result = await execute(change, self.call_mfp)
        self.changes.finish(change.id, result)
        text = result_text(change, result)
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        done = ", ".join(f"{o['item']} {'ok' if o['ok'] else 'FAILED: ' + (o['error'] or '')}" for o in result["outcomes"])
        self.history.note(chat_id, f"The user confirmed card {change.id} for {change.date}: {done}")
        logger.info("card %s executed: %s", change.id, done)

    # --- misc --------------------------------------------------------------

    def _log_usage(self, chat_id: int, result, seconds: float) -> None:
        usage = result.usage
        tools = [
            part.tool_name
            for m in result.new_messages()
            for part in getattr(m, "parts", [])
            if isinstance(part, ToolCallPart)
        ]
        record = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "chat_id": chat_id,
            "model": self.model,
            "requests": usage.requests,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_tokens": getattr(usage, "cache_read_tokens", None),
            "tools": tools,
            "seconds": round(seconds, 1),
        }
        logger.info("run: %s", json.dumps(record))
        with self.usage_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


@contextlib.asynccontextmanager
async def typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    async def loop():
        while True:
            with contextlib.suppress(Exception):
                await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
            await asyncio.sleep(4)

    task = asyncio.create_task(loop())
    try:
        yield
    finally:
        task.cancel()


async def transcribe(audio: bytes) -> str:
    """Voice note (ogg/opus) -> text with whisper.cpp, language auto-detected."""
    with tempfile.TemporaryDirectory() as tmp:
        src, wav = Path(tmp) / "in", Path(tmp) / "in.wav"
        src.write_bytes(audio)
        await _run("ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(src), "-ar", "16000", "-ac", "1", str(wav))
        out = await _run(
            WHISPER_CLI, "-m", WHISPER_MODEL, "-l", "auto", "-nt", "-np", "-t", str(os.cpu_count() or 4), "-f", str(wav)
        )
    return " ".join(out.split())


async def _run(*cmd: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"{Path(cmd[0]).name} failed: {stderr.decode(errors='replace').strip()[-300:]}")
    return stdout.decode(errors="replace")


def _plain(html_text: str) -> str:
    return re.sub(r"<[^>]+>", "", html_text).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'").replace("\n", " / ")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Network hiccups (polling retries by itself) get one line; anything else a traceback."""
    if isinstance(context.error, NetworkError):
        logger.warning("telegram network error: %s", context.error)
    else:
        logger.error("unhandled error", exc_info=context.error)


def _chunks(text: str):
    while text:
        yield text[:TELEGRAM_LIMIT]
        text = text[TELEGRAM_LIMIT:]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines contain the bot token URL
    env = load_env()
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_ID"):
        if not env.get(key):
            raise SystemExit(f"fa-bot: {key} is not set (.env)")
    for key, value in env.items():  # provider settings for pydantic-ai, from .env on the host
        if key.endswith(("_API_KEY", "_BASE_URL")) and value:
            os.environ.setdefault(key, value)
    bot = Bot(env)

    async def post_init(app: Application) -> None:
        await app.bot.set_my_commands([])

    app = Application.builder().token(env["TELEGRAM_BOT_TOKEN"]).post_init(post_init).build()
    app.add_handler(
        MessageHandler(
            filters.User(bot.allowed) & (filters.TEXT | filters.VOICE | filters.AUDIO | filters.PHOTO) & ~filters.COMMAND,
            bot.on_message,
        )
    )
    app.add_handler(CallbackQueryHandler(bot.on_tap))
    app.add_error_handler(on_error)
    logger.info("fa-bot polling with model %s", bot.model)
    app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=False)
