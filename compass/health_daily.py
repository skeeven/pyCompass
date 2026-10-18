"""Owner-scoped daily wellness logs and non-diagnostic weekly summaries."""

import json
import math
from datetime import date, timedelta

FIELDS = {
    "weight_lb": (50, 1000),
    "waist_in": (10, 100),
    "sleep_hours": (0, 24),
    "cpap_hours": (0, 24),
    "energy": (1, 10),
    "stress": (1, 10),
    "hunger": (1, 10),
    "movement_minutes": (0, 1440),
    "downtime_minutes": (0, 1440),
    "nutrition_on_track": (0, 1),
    "nutrition_note": None,
    "notes": None,
}


def validate_log(data):
    """Allow missing answers, but never assume missing means zero."""
    if not isinstance(data, dict) or set(data) - set(FIELDS):
        raise ValueError("Unknown daily health field.")
    clean = {}
    for key, value in data.items():
        if value is None or value == "":
            continue
        bounds = FIELDS[key]
        if bounds is None:
            if not isinstance(value, str) or len(value) > 2000:
                raise ValueError(f"Invalid value for {key}.")
            clean[key] = value
        else:
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or not bounds[0] <= value <= bounds[1]):
                raise ValueError(f"Invalid value for {key}.")
            clean[key] = value
    return clean


class DailyHealthService:
    """A logged-in account can only access its own daily health entries."""

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id
        with db.connect() as conn:
            if not conn.execute(
                "SELECT 1 FROM users WHERE id = ?", (user_id,)
            ).fetchone():
                raise ValueError("An authenticated account is required.")

    def save(self, day, data):
        if not isinstance(day, date) or day > date.today():
            raise ValueError("Choose today or a previous day.")
        payload = json.dumps(validate_log(data))
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO health_daily_logs (user_id, day, log_json)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, day)
                   DO UPDATE SET log_json = excluded.log_json""",
                (self.user_id, day.isoformat(), payload),
            )

    def get(self, day):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT log_json FROM health_daily_logs "
                "WHERE user_id = ? AND day = ?",
                (self.user_id, day.isoformat()),
            ).fetchone()
        return json.loads(row[0]) if row else {}

    def history(self, start=None, end=None):
        if start is not None and end is not None and start > end:
            raise ValueError("Invalid history range.")
        sql = "SELECT day, log_json FROM health_daily_logs WHERE user_id = ?"
        args = [self.user_id]
        if start is not None:
            sql += " AND day >= ?"
            args.append(start.isoformat())
        if end is not None:
            sql += " AND day <= ?"
            args.append(end.isoformat())
        sql += " ORDER BY day"
        with self.db.connect() as conn:
            rows = conn.execute(sql, tuple(args)).fetchall()
        return [{"day": day, **json.loads(value)} for day, value in rows]

    def delete(self, day):
        with self.db.connect() as conn:
            conn.execute(
                "DELETE FROM health_daily_logs WHERE user_id = ? AND day = ?",
                (self.user_id, day.isoformat()),
            )


def weekly_summary(rows, end_day):
    """Simple descriptive averages for actually recorded values only."""
    start = end_day - timedelta(days=6)
    current = [
        r for r in rows
        if start.isoformat() <= r["day"] <= end_day.isoformat()
    ]
    means = {}
    for key, bounds in FIELDS.items():
        if bounds is None:
            continue
        values = [r[key] for r in current if key in r]
        if values:
            means[key] = sum(values) / len(values)
    return {"start": start, "end": end_day, "days_logged": len(current),
            "averages": means}
