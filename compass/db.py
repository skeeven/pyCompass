"""SQLite storage with an optional SQLiteCloud connection."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        locked_until REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS checkins (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        day TEXT NOT NULL,
        mood INTEGER NOT NULL CHECK(mood BETWEEN 1 AND 10),
        energy INTEGER NOT NULL CHECK(energy BETWEEN 1 AND 10),
        stress INTEGER NOT NULL CHECK(stress BETWEEN 1 AND 10),
        sleep REAL NOT NULL CHECK(sleep BETWEEN 0 AND 24),
        note TEXT NOT NULL,
        UNIQUE(user_id, day)
    )""",
    """CREATE TABLE IF NOT EXISTS journal (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        tags TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
        content TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS insights (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('observation', 'weekly')),
        content TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending', 'approved', 'dismissed'))
    )""",
    "CREATE INDEX IF NOT EXISTS journal_owner ON journal(user_id)",
    "CREATE INDEX IF NOT EXISTS messages_owner ON messages(user_id)",
    "CREATE INDEX IF NOT EXISTS insights_owner ON insights(user_id)",
)
SCHEMA_VERSION = 1


class Database:
    """Create short-lived connections; never cache a user's result set."""

    def __init__(self, settings):
        self.settings = settings

    @contextmanager
    def connect(self):
        """Commit successful work and roll back failures."""
        if self.settings.database_url:
            import sqlitecloud

            conn = sqlitecloud.connect(self.settings.database_url)
        else:
            path = Path(self.settings.database_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, timeout=10)
            conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        """Record the baseline version without resetting existing records."""
        with self.connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            row = conn.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()
            version = row[0] or 0
            if version > SCHEMA_VERSION:
                raise ValueError(
                    "The database requires a newer version of Compass."
                )
            if version == SCHEMA_VERSION:
                return
            for statement in SCHEMA:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
