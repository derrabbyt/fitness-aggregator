"""Short conversation memory per chat: the last few exchanges of the last hours,
in SQLite (state/bot/bot.db).

Only what was said is kept: the user's messages, the bot's replies, and notes
about cards (shown, confirmed, cancelled). Tool calls and their results (food
searches, day listings) are dropped: they made every later message carry tens
of thousands of tokens, and the model looks things up again when it needs to.
Photos are kept as a placeholder."""

import sqlite3
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from pydantic_ai.messages import (
    BinaryContent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

MAX_AGE_SECONDS = 6 * 3600
MAX_RUNS = 10  # one run = a user message and everything the agent did for it


class History:
    def __init__(self, path: Path | str, clock: Callable[[], float] = time.time):
        self.clock = clock
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, chat_id INTEGER, ts REAL, messages TEXT)"
        )

    def load(self, chat_id: int) -> list[ModelMessage]:
        rows = self.db.execute(
            "SELECT messages FROM history WHERE chat_id = ? AND ts > ? ORDER BY id DESC LIMIT ?",
            (chat_id, self.clock() - MAX_AGE_SECONDS, MAX_RUNS),
        ).fetchall()
        messages: list[ModelMessage] = []
        for (raw,) in reversed(rows):
            messages.extend(compact(ModelMessagesTypeAdapter.validate_json(raw)))  # rows saved before compacting
        return messages

    def save(self, chat_id: int, messages: list[ModelMessage]) -> None:
        stripped = compact(messages)
        if not stripped:
            return
        self.db.execute(
            "INSERT INTO history (chat_id, ts, messages) VALUES (?, ?, ?)",
            (chat_id, self.clock(), ModelMessagesTypeAdapter.dump_json(stripped).decode()),
        )
        self.db.execute("DELETE FROM history WHERE ts < ?", (self.clock() - MAX_AGE_SECONDS,))

    def note(self, chat_id: int, text: str) -> None:
        """Record something that happened outside a model run (a card tapped), so
        the next run knows, e.g. for "remove it again"."""
        self.save(
            chat_id,
            [ModelRequest(parts=[UserPromptPart(content=f"[bot event] {text}")]), ModelResponse(parts=[TextPart("Noted.")])],
        )


def compact(messages: list[ModelMessage]) -> list[ModelMessage]:
    """User prompts (photos as "[photo]") and the model's text replies only,
    as alternating request/response pairs."""
    out: list[ModelMessage] = []
    for message in messages:
        if isinstance(message, ModelRequest):
            parts = []
            for part in message.parts:
                if not isinstance(part, UserPromptPart):
                    continue  # tool returns, retry prompts
                if not isinstance(part.content, str):
                    part = replace(part, content=["[photo]" if isinstance(c, BinaryContent) else c for c in part.content])
                parts.append(part)
            if parts:
                out.append(ModelRequest(parts=parts))
        elif isinstance(message, ModelResponse):
            text = "".join(p.content for p in message.parts if isinstance(p, TextPart)).strip()
            if text and out and isinstance(out[-1], ModelRequest):
                out.append(ModelResponse(parts=[TextPart(text)]))
            elif text and out and isinstance(out[-1], ModelResponse):
                out[-1] = ModelResponse(parts=[TextPart(out[-1].parts[0].content + "\n" + text)])
    if out and isinstance(out[-1], ModelRequest):
        out.append(ModelResponse(parts=[TextPart("(no reply)")]))
    return out

