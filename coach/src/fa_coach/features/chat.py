"""The coach chat: every free-text message not taken by another handler goes
to the model with the coach-chat and context-log skills and every registered
tool. Only a short history is kept (the last few exchanges, recent ones)."""

import datetime
import logging

from ..ports import ChatTurn, ModelError
from ..registry import registry

logger = logging.getLogger("fa-coach")

SKILLS = ("coach-chat", "context-log")
HISTORY_TURNS = 6  # user + coach messages sent back to the model
HISTORY_MAX_AGE = datetime.timedelta(hours=12)
NO_ANSWER = "I don't have an answer to that."


@registry.text(order=1000)  # last: more specific handlers go first
async def chat(coach, text: str, now: datetime.datetime) -> bool:
    try:
        answer = await coach.ask(SKILLS, {"message": text}, history=_history(coach, now), now=now)
    except ModelError as exc:
        coach.say(f"⚠️ The coach model can't be reached right now ({exc}). Try again later.")
        return True
    reply = answer.text or NO_ANSWER
    coach.say(reply)
    _remember(coach, now, ChatTurn("user", text), ChatTurn("assistant", reply))
    return True


def _history(coach, now: datetime.datetime) -> list[ChatTurn]:
    rows = coach.db.all(
        "SELECT role, text FROM chat_history WHERE at >= ? ORDER BY id DESC LIMIT ?",
        ((now - HISTORY_MAX_AGE).isoformat(), HISTORY_TURNS),
    )
    turns = [ChatTurn(r["role"], r["text"]) for r in reversed(rows)]
    while turns and turns[0].role != "user":  # the model's history starts with the user
        turns.pop(0)
    return turns


def _remember(coach, now: datetime.datetime, *turns: ChatTurn) -> None:
    with coach.db.transaction():
        for turn in turns:
            coach.db.execute(
                "INSERT INTO chat_history (at, role, text) VALUES (?, ?, ?)", (now.isoformat(), turn.role, turn.text)
            )
        # Only the short history is ever read; older turns are dropped.
        coach.db.execute(
            "DELETE FROM chat_history WHERE id NOT IN (SELECT id FROM chat_history ORDER BY id DESC LIMIT ?)",
            (HISTORY_TURNS,),
        )
