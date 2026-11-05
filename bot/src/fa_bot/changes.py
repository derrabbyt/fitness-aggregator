"""Diary changes that wait for the user's tap, and their one-time execution.

The model never writes to MyFitnessPal. It can only propose a Change (foods to
add from a draft, entries to remove), which the bot shows as a card with
✅/❌ buttons. Only `ChangeStore.claim` turns a pending card into one that runs,
and only once: the status moves pending -> running in a single UPDATE, so a
double tap, a second bot process, or a restart can't run it twice. Each write
is sent exactly once and never retried; afterwards the day is read back so the
user sees what is actually in the diary.
"""

import datetime
import json
import sqlite3
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

EXPIRY_SECONDS = 30 * 60
OLD_DAYS_WARNING = 7

# (tool name, arguments) -> result; raises on failure. The real one calls the
# mfp MCP server; tests pass a fake.
CallTool = Callable[[str, dict[str, Any]], Awaitable[Any]]


@dataclass
class Add:
    draft_id: str
    option: int
    serving: int
    name: str
    serving_label: str | None
    quantity: float
    meal: str
    kcal: float | None
    protein: float | None
    carbs: float | None
    fat: float | None
    brand: str | None = None


@dataclass
class QuickAdd:
    label: str  # what the estimate is for; MFP only stores "Quick Add"
    meal: str
    kcal: float
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None


QUICK_ADD_NAME = "quick add"  # how Quick Add entries are named in the diary


@dataclass
class Remove:
    name: str  # exact entry name from the day listing
    meal: str
    kcal: float | None


@dataclass
class Change:
    chat_id: int
    date: str  # YYYY-MM-DD
    adds: list[Add] = field(default_factory=list)
    removes: list[Remove] = field(default_factory=list)
    quick_adds: list[QuickAdd] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    message_id: int | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "Change":
        data = json.loads(raw)
        data["adds"] = [Add(**a) for a in data["adds"]]
        data["removes"] = [Remove(**r) for r in data["removes"]]
        data["quick_adds"] = [QuickAdd(**q) for q in data.get("quick_adds") or []]
        return cls(**data)


class ChangeStore:
    """Cards in SQLite (state/bot/bot.db), so a restart can't lose or rerun one."""

    def __init__(self, path: Path | str, clock: Callable[[], float] = time.time):
        self.clock = clock
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS changes (id TEXT PRIMARY KEY, chat_id INTEGER, "
            "status TEXT NOT NULL, body TEXT NOT NULL, created_at REAL NOT NULL, result TEXT)"
        )

    def add(self, change: Change) -> list[Change]:
        """Store a new pending card. Older pending cards in the chat are superseded
        (a correction replaces the previous card); they're returned so their
        messages can be updated."""
        superseded = [
            Change.from_json(body)
            for (body,) in self.db.execute(
                "SELECT body FROM changes WHERE chat_id = ? AND status = 'pending'", (change.chat_id,)
            )
        ]
        self.db.execute(
            "UPDATE changes SET status = 'superseded' WHERE chat_id = ? AND status = 'pending'",
            (change.chat_id,),
        )
        self.db.execute(
            "INSERT INTO changes (id, chat_id, status, body, created_at) VALUES (?, ?, 'pending', ?, ?)",
            (change.id, change.chat_id, change.to_json(), change.created_at),
        )
        return superseded

    def set_message(self, change: Change, message_id: int) -> None:
        change.message_id = message_id
        self.db.execute("UPDATE changes SET body = ? WHERE id = ?", (change.to_json(), change.id))

    def get(self, change_id: str) -> tuple[Change, str] | None:
        row = self.db.execute("SELECT body, status FROM changes WHERE id = ?", (change_id,)).fetchone()
        return (Change.from_json(row[0]), row[1]) if row else None

    def claim(self, change_id: str, chat_id: int) -> tuple[str, Change | None]:
        """Atomically move a pending card to running. Returns ("ok", change) for the
        one caller that may execute it, otherwise the reason and the change."""
        found = self.get(change_id)
        if not found or found[0].chat_id != chat_id:
            return "unknown", None
        change, status = found
        if status != "pending":
            return status, change
        if self.clock() - change.created_at > EXPIRY_SECONDS:
            self.db.execute("UPDATE changes SET status = 'expired' WHERE id = ? AND status = 'pending'", (change_id,))
            return "expired", change
        cur = self.db.execute("UPDATE changes SET status = 'running' WHERE id = ? AND status = 'pending'", (change_id,))
        return ("ok", change) if cur.rowcount == 1 else ("running", change)

    def cancel(self, change_id: str, chat_id: int) -> tuple[str, Change | None]:
        found = self.get(change_id)
        if not found or found[0].chat_id != chat_id:
            return "unknown", None
        cur = self.db.execute("UPDATE changes SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (change_id,))
        return ("ok" if cur.rowcount == 1 else found[1]), found[0]

    def finish(self, change_id: str, result: dict) -> None:
        self.db.execute(
            "UPDATE changes SET status = 'done', result = ? WHERE id = ?", (json.dumps(result), change_id)
        )


@dataclass
class Outcome:
    item: str
    ok: bool
    error: str | None = None
    match: str = ""  # diary name prefix used to check whether a failed write landed anyway
    kind: str = "add"  # add | remove


async def execute(change: Change, call: CallTool) -> dict:
    """Run a claimed change: adds first (so a failed add never costs an entry
    during a replace), then removes. Each write is sent once; failures are
    recorded, not retried. The day is read before and after, so a failed call
    that went through anyway (e.g. a timeout) is reported as such."""
    before = await _entry_counts(change.date, call)
    outcomes: list[Outcome] = []
    for add in change.adds:
        try:
            await call(
                "fitness_log_food",
                {
                    "draft_id": add.draft_id,
                    "option": add.option,
                    "serving": add.serving,
                    "quantity": add.quantity,
                    "meal": add.meal,
                    "date": change.date,
                },
            )
            outcomes.append(Outcome(f"+ {add.name}", True, match=_norm(add.name)))
        except Exception as exc:  # noqa: BLE001 - reported to the user, never retried
            outcomes.append(Outcome(f"+ {add.name}", False, _short(exc), match=_norm(add.name)))
    for qa in change.quick_adds:
        label = f"+ Quick Add {qa.kcal:.0f} kcal ({qa.label})"
        try:
            await call(
                "fitness_quick_add",
                {"calories": qa.kcal, "protein": qa.protein, "carbs": qa.carbs, "fat": qa.fat, "meal": qa.meal, "date": change.date},
            )
            outcomes.append(Outcome(label, True, match=QUICK_ADD_NAME))
        except Exception as exc:  # noqa: BLE001
            outcomes.append(Outcome(label, False, _short(exc), match=QUICK_ADD_NAME))
    for remove in change.removes:
        try:
            await call("fitness_delete_food", {"query": remove.name, "meal": remove.meal, "date": change.date})
            outcomes.append(Outcome(f"− {remove.name}", True, match=_norm(remove.name), kind="remove"))
        except Exception as exc:  # noqa: BLE001
            outcomes.append(Outcome(f"− {remove.name}", False, _short(exc), match=_norm(remove.name), kind="remove"))

    day: dict | None = None
    day_error = None
    try:
        day = await call("fitness_get_day", {"date": change.date})
    except Exception as exc:  # noqa: BLE001
        day_error = _short(exc)

    if before is not None and day is not None:
        after = _counts(day)
        for outcome in outcomes:
            if outcome.ok:
                continue
            delta = _matching(after, outcome.match) - _matching(before, outcome.match)
            if outcome.kind == "add" and delta > 0:
                outcome.error = f"{outcome.error} (but it is in the diary now)"
            elif outcome.kind == "remove" and delta < 0:
                outcome.error = f"{outcome.error} (but it is gone from the diary now)"
    return {
        "outcomes": [{"item": o.item, "ok": o.ok, "error": o.error} for o in outcomes],
        "nutrition": (day or {}).get("nutrition"),
        "day_error": day_error,
    }


async def _entry_counts(date: str, call: CallTool) -> dict[str, int] | None:
    try:
        return _counts(await call("fitness_get_day", {"date": date}))
    except Exception:  # noqa: BLE001 - only used to explain failures
        return None


def _matching(counts: dict[str, int], prefix: str) -> int:
    return sum(n for name, n in counts.items() if name.startswith(prefix))


def _counts(day: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in day.get("diary") or []:
        name = _norm(entry.get("name"))
        counts[name] = counts.get(name, 0) + 1
    return counts


def _norm(name: str | None) -> str:
    return " ".join((name or "").replace(" ", " ").lower().split())


def _short(exc: BaseException, limit: int = 300) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text if len(text) <= limit else text[: limit - 1] + "…"


def is_old(date: str, today: datetime.date | None = None) -> bool:
    today = today or datetime.date.today()
    return (today - datetime.date.fromisoformat(date)).days > OLD_DAYS_WARNING
