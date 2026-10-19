"""Phase 4 read model for original Today and later Health daily observations.

No destructive migration: both owner-scoped historical tables remain intact.
Per-field provenance identifies overlaps; Health observations take priority
for shared numeric fields when pre-existing data disagrees.
"""

import json
from datetime import date

from compass.health_daily import DailyHealthService

HEALTH_SHARED = ("energy", "stress", "sleep_hours")
LEGACY_SHARED = {"sleep": "sleep_hours", "energy": "energy", "stress": "stress"}


def reconcile_daily(legacy_rows, health_rows):
    """One calendar-day view with per-field sources and flagged conflicts."""
    combined = {}
    for row in legacy_rows:
        day = row["day"]
        record = combined.setdefault(day, {"day": day, "values": {},
                                          "sources": {}, "conflicts": {}})
        for key, value in row.items():
            if key in {"id", "user_id", "day"}:
                continue
            field = LEGACY_SHARED.get(key, key)
            record["values"][field] = value
            record["sources"][field] = "Today"
    for row in health_rows:
        day = row["day"]
        record = combined.setdefault(day, {"day": day, "values": {},
                                          "sources": {}, "conflicts": {}})
        for key, value in row.items():
            if key == "day":
                continue
            if key in record["values"] and record["values"][key] != value:
                record["conflicts"][key] = {
                    "today": record["values"][key],
                    "health": value,
                }
            record["values"][key] = value
            record["sources"][key] = "Health"
    return [combined[day] for day in sorted(combined)]


class UnifiedDailyService:
    def __init__(self, db, user_id):
        self.db, self.user_id = db, user_id
        self.health = DailyHealthService(db, user_id)
        with db.connect() as conn:
            if not conn.execute("SELECT 1 FROM users WHERE id = ?",
                                (user_id,)).fetchone():
                raise ValueError("An authenticated account is required.")

    def history(self, start=None, end=None):
        from compass.repository import Repository
        legacy = Repository(self.db, self.user_id).rows("checkins")
        if start:
            legacy = [r for r in legacy if r["day"] >= start.isoformat()]
        if end:
            legacy = [r for r in legacy if r["day"] <= end.isoformat()]
        return reconcile_daily(legacy, self.health.history(start, end))

    def get(self, day):
        result = self.history(start=day, end=day)
        return result[0] if result else {
            "day": day.isoformat(), "values": {}, "sources": {}, "conflicts": {}
        }

    def save_today(self, day, mood, energy, stress, sleep, note, *,
                   emotions=(), contexts=(), needs="", activity_done=False):
        """Atomically preserve Today metadata and synchronize shared Health data."""
        from compass.checkin import CONTEXTS, EMOTIONS
        from compass.health_daily import validate_log
        from uuid import uuid4
        if not isinstance(day, date) or day > date.today():
            raise ValueError("Invalid check-in date.")
        if any(isinstance(v, bool) or not isinstance(v, int)
               or not 1 <= v <= 10 for v in (mood, energy, stress)):
            raise ValueError("Ratings must be from 1 to 10.")
        if isinstance(sleep, bool) or not isinstance(sleep, (float, int)) or not 0 <= sleep <= 24:
            raise ValueError("Sleep must be between 0 and 24 hours.")
        if not isinstance(note, str) or not isinstance(needs, str):
            raise ValueError("Invalid notes.")
        if any(tag not in EMOTIONS for tag in emotions) or any(
                tag not in CONTEXTS for tag in contexts):
            raise ValueError("Invalid feelings or contexts.")
        if len(note) > 2000 or len(needs) > 1000:
            raise ValueError("Notes exceed the allowed length.")
        health_patch = validate_log({
            "energy": energy, "stress": stress, "sleep_hours": sleep
        })
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT log_json FROM health_daily_logs WHERE user_id=? AND day=?",
                (self.user_id, day.isoformat())
            ).fetchone()
            merged = json.loads(row[0]) if row else {}
            merged.update(health_patch)
            conn.execute(
                """INSERT INTO health_daily_logs (user_id, day, log_json)
                VALUES (?, ?, ?) ON CONFLICT(user_id, day)
                DO UPDATE SET log_json=excluded.log_json""",
                (self.user_id, day.isoformat(), json.dumps(merged))
            )
            conn.execute(
                """INSERT INTO checkins
                (id, user_id, day, mood, energy, stress, sleep, note,
                 emotions, contexts, needs, activity_done)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET
                  mood=excluded.mood, energy=excluded.energy,
                  stress=excluded.stress, sleep=excluded.sleep,
                  note=excluded.note, emotions=excluded.emotions,
                  contexts=excluded.contexts, needs=excluded.needs,
                  activity_done=excluded.activity_done""",
                (str(uuid4()), self.user_id, day.isoformat(),
                 mood, energy, stress, sleep, note,
                 json.dumps(list(dict.fromkeys(emotions))),
                 json.dumps(list(dict.fromkeys(contexts))),
                 needs, int(bool(activity_done))),
            )

    def save_health(self, day, updates):
        """Merge Health details and sync existing Today ratings, if present.

        Never manufacture a Today mood, notes, or activity completion record.
        """
        from compass.health_daily import validate_log
        if not isinstance(day, date) or day > date.today():
            raise ValueError("Invalid check-in date.")
        updates = validate_log(updates)
        with self.db.connect() as conn:
            existing = conn.execute(
                "SELECT log_json FROM health_daily_logs WHERE user_id=? AND day=?",
                (self.user_id, day.isoformat())
            ).fetchone()
            full = json.loads(existing[0]) if existing else {}
            full.update(updates)
            conn.execute(
                """INSERT INTO health_daily_logs (user_id, day, log_json)
                VALUES (?, ?, ?) ON CONFLICT(user_id, day)
                DO UPDATE SET log_json=excluded.log_json""",
                (self.user_id, day.isoformat(), json.dumps(full)),
            )
            shared = {
                "energy": "energy", "stress": "stress", "sleep_hours": "sleep"
            }
            assignments = [(legacy, updates[key]) for key, legacy in shared.items()
                           if key in updates]
            if assignments:
                conn.execute(
                    "UPDATE checkins SET " +
                    ", ".join(field + " = ?" for field, _ in assignments) +
                    " WHERE user_id=? AND day=?",
                    tuple(value for _, value in assignments) +
                    (self.user_id, day.isoformat()),
                )

    def delete_health(self, day):
        """Health-only deletion does not erase an independent Today record."""
        self.health.delete(day)
