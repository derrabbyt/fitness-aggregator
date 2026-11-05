"""Short conversation memory per chat: the last few exchanges of the last hours,
in SQLite (state/bot/bot.db). Photos are not kept, only a placeholder."""

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
            messages.extend(ModelMessagesTypeAdapter.validate_json(raw))
        return messages

    def save(self, chat_id: int, messages: list[ModelMessage]) -> None:
        stripped = [_strip_binary(m) for m in messages]
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


def _strip_binary(message: ModelMessage) -> ModelMessage:
    if not isinstance(message, ModelRequest):
        return message
    parts = []
    for part in message.parts:
        if isinstance(part, UserPromptPart) and not isinstance(part.content, str):
            content = ["[photo]" if isinstance(c, BinaryContent) else c for c in part.content]
            part = replace(part, content=content)
        parts.append(part)
    return replace(message, parts=parts)

