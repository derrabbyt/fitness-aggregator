-- The coach chat's short history (features/chat.py keeps only the last few turns).
CREATE TABLE chat_history (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    at   TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text TEXT NOT NULL
);
