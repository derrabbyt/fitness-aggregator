-- Core tables (ticket 01).

-- Keys for Database.once(): "do this once per day/week/session" rules.
CREATE TABLE once_keys (
    key TEXT PRIMARY KEY,
    at  TEXT NOT NULL
);

-- Telegram message ids of outbox messages sent with a ref, so an Edit can
-- replace their text and buttons later (telegram_adapter.py).
CREATE TABLE sent_messages (
    ref        TEXT PRIMARY KEY,
    chat_id    INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    sent_at    TEXT NOT NULL
);
