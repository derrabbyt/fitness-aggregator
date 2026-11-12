"""The coach's SQLite database (state/coach/coach.db). Only the coach opens it.

Tables come from `migrations/*.sql`, applied once each in file-name order and
recorded by name, so two tickets can each add `NN_<name>.sql` without
colliding.
"""

import contextlib
import datetime
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

MIGRATIONS = Path(__file__).parent / "migrations"


class Database:
    def __init__(self, path: Path | str, migrations: Path = MIGRATIONS):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._migrate(migrations)

    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def all(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def value(self, sql: str, params: tuple | dict = ()) -> Any:
        row = self.one(sql, params)
        return row[0] if row else None

    @contextlib.contextmanager
    def transaction(self) -> Iterator[None]:
        """All statements inside commit together or not at all."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

    def once(self, key: str, now: datetime.datetime) -> bool:
        """True the first time `key` is seen, False ever after (atomic, survives
        restarts). For "once per day/week/session" rules, e.g.
        `once(f"evening-reminder:{today}")`."""
        cur = self.execute("INSERT OR IGNORE INTO once_keys (key, at) VALUES (?, ?)", (key, now.isoformat()))
        return cur.rowcount == 1

    def once_at(self, key: str) -> datetime.datetime | None:
        """When `once(key)` first saw `key`, or None if it never did."""
        at = self.value("SELECT at FROM once_keys WHERE key = ?", (key,))
        return datetime.datetime.fromisoformat(at) if at else None

    def _migrate(self, folder: Path) -> None:
        self.execute("CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        done = {row[0] for row in self.all("SELECT name FROM migrations")}
        for path in sorted(folder.glob("*.sql")):
            if path.name in done:
                continue
            # executescript commits on its own, so the script and its record
            # go in one explicit transaction.
            self.conn.executescript(
                f"BEGIN;\n{path.read_text(encoding='utf-8')}\n;"
                f"INSERT INTO migrations (name, applied_at) VALUES ('{path.name}', datetime('now'));\nCOMMIT;"
            )
