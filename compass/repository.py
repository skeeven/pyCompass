"""User-scoped data access for all wellness records."""

import json
from datetime import datetime, timezone
from uuid import uuid4

TABLES = {"checkins", "journal", "messages", "insights"}


def now():
    """Return an ISO timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


class Repository:
    """Bind every operation to an authenticated account id."""

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id
        with db.connect() as conn:
            if not conn.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone():
                raise ValueError("An authenticated account is required.")

    def rows(self, table):
        """Read this user's records in chronological order."""
        if table not in TABLES:
            raise ValueError("Unknown record type.")
        order = "day" if table == "checkins" else "created_at"
        with self.db.connect() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {table} WHERE user_id = ? "
                f"ORDER BY {order}, id",
                (self.user_id,),
            )
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]

    def save_checkin(
        self,
        day,
        mood,
        energy,
        stress,
        sleep,
        note,
        *,
        emotions=(),
        contexts=(),
        needs="",
        activity_done=False,
    ):
        """Save one check-in per day, replacing an earlier check-in."""
        from datetime import date

        date.fromisoformat(day)
        if any(not 1 <= v <= 10 for v in (mood, energy, stress)):
            raise ValueError("Ratings must be between 1 and 10.")
        if not 0 <= sleep <= 24:
            raise ValueError("Sleep must be between 0 and 24 hours.")
        from compass.checkin import CONTEXTS, EMOTIONS

        if any(tag not in EMOTIONS for tag in emotions):
            raise ValueError("Unknown emotion tag.")
        if any(tag not in CONTEXTS for tag in contexts):
            raise ValueError("Unknown context tag.")
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO checkins
                (id, user_id, day, mood, energy, stress, sleep, note,
                emotions, contexts, needs, activity_done)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET
                mood = excluded.mood, energy = excluded.energy,
                stress = excluded.stress, sleep = excluded.sleep,
                note = excluded.note, emotions = excluded.emotions,
                contexts = excluded.contexts, needs = excluded.needs,
                activity_done = excluded.activity_done""",
                (
                    str(uuid4()),
                    self.user_id,
                    day,
                    mood,
                    energy,
                    stress,
                    sleep,
                    note[:2000],
                    json.dumps(list(dict.fromkeys(emotions))),
                    json.dumps(list(dict.fromkeys(contexts))),
                    needs.strip()[:1000],
                    int(bool(activity_done)),
                ),
            )

    def add_journal(self, title, body, tags):
        """Store a nonempty journal entry."""
        if not body.strip():
            raise ValueError("Write something before saving.")
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO journal VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    self.user_id,
                    now(),
                    title.strip()[:120],
                    body.strip()[:12000],
                    tags[:300],
                ),
            )

    def add_exchange(self, user_text, assistant_text):
        """Store a complete chat exchange in one transaction."""
        with self.db.connect() as conn:
            for role, content in (
                ("user", user_text),
                ("assistant", assistant_text),
            ):
                conn.execute(
                    "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
                    (str(uuid4()), self.user_id, now(), role, content),
                )

    def add_insight(self, content, kind="observation"):
        """Store an AI suggestion pending explicit user review."""
        if kind not in {"observation", "weekly"}:
            raise ValueError("Unknown insight type.")
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO insights
                (id, user_id, created_at, kind, content)
                VALUES (?, ?, ?, ?, ?)""",
                (str(uuid4()), self.user_id, now(), kind, content),
            )

    def review_insight(self, insight_id, status):
        """Approve or dismiss only an insight owned by this account."""
        if status not in {"approved", "dismissed"}:
            raise ValueError("Invalid review status.")
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE insights SET status = ? WHERE id = ? AND user_id = ?",
                (status, insight_id, self.user_id),
            )

    def delete(self, table, record_id):
        """Delete only an owned record from an allowlisted table."""
        if table not in TABLES:
            raise ValueError("Unknown record type.")
        with self.db.connect() as conn:
            conn.execute(
                f"DELETE FROM {table} WHERE id = ? AND user_id = ?",
                (record_id, self.user_id),
            )

    def export(self):
        """Return an account's wellness data as JSON, excluding credentials."""
        return json.dumps(
            {table: self.rows(table) for table in sorted(TABLES)}, indent=2
        )

    def delete_account(self):
        """Delete this user's records and account in a single transaction."""
        with self.db.connect() as conn:
            for table in sorted(TABLES):
                conn.execute(
                    f"DELETE FROM {table} WHERE user_id = ?",
                    (self.user_id,),
                )
            conn.execute("DELETE FROM users WHERE id = ?", (self.user_id,))
