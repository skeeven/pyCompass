"""Privacy-minimized, idempotent import of Sleep Cycle's semicolon CSV export."""

import csv
import io
import math
from datetime import datetime, timedelta

MAX_CSV_BYTES = 8 * 1024 * 1024
MAX_CSV_ROWS = 20000
REQUIRED = {
    "Start", "End", "Sleep Quality", "Time asleep (seconds)",
    "Time in bed (seconds)",
}


def _hours(value, label):
    """Missing sleep duration isn't an invented zero."""
    if not value.strip():
        return None
    try:
        seconds = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {label} in Sleep Cycle export.") from exc
    if not math.isfinite(seconds) or not 0 <= seconds <= 86400:
        raise ValueError(f"Invalid {label} in Sleep Cycle export.")
    return round(seconds / 3600, 4) if seconds else None


def _quality(value):
    if not value.strip():
        return None
    try:
        number = float(value.strip().removesuffix("%").strip())
    except ValueError as exc:
        raise ValueError("Invalid Sleep Quality percentage.") from exc
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise ValueError("Invalid Sleep Quality percentage.")
    return number


def parse_sleep_cycle_csv(data):
    """Extract only session time, duration, and quality; discard other CSV data."""
    if not data or len(data) > MAX_CSV_BYTES:
        raise ValueError("CSV must be non-empty and at most 8 MB.")
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc
    # The official export uses a semicolon separator, regardless of extension.
    reader = csv.DictReader(io.StringIO(decoded), delimiter=";")
    if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
        raise ValueError("Unrecognized Sleep Cycle CSV columns.")
    output = []
    seen = set()
    for line, row in enumerate(reader, start=2):
        if line > MAX_CSV_ROWS + 1:
            raise ValueError("CSV exceeds the 20,000-session limit.")
        if None in row or any(row.get(key) is None for key in REQUIRED):
            raise ValueError(f"Malformed Sleep Cycle CSV row {line}.")
        try:
            start = datetime.strptime(row["Start"].strip(), "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(row["End"].strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise ValueError(f"Invalid session timestamp in row {line}.") from exc
        if not start < end <= start + timedelta(hours=24):
            raise ValueError(f"Invalid sleep session duration in row {line}.")
        sleep_hours = _hours(row["Time asleep (seconds)"], "time asleep")
        bed_hours = _hours(row["Time in bed (seconds)"], "time in bed")
        quality = _quality(row["Sleep Quality"])
        if sleep_hours is not None and bed_hours is not None and sleep_hours > bed_hours + 0.1:
            raise ValueError(f"Sleep duration exceeds time in bed in row {line}.")
        key = (start.isoformat(sep=" "), end.isoformat(sep=" "))
        if key in seen:
            continue
        seen.add(key)
        output.append({
            "session_start": key[0],
            "session_end": key[1],
            "night": end.date().isoformat(),
            "sleep_quality_pct": quality,
            "sleep_hours": sleep_hours,
            "time_in_bed_hours": bed_hours,
        })
    if not output:
        raise ValueError("CSV contains no sleep sessions.")
    return output


class SleepCycleCSVService:
    """All queries are scoped to the authenticated account."""

    def __init__(self, db, user_id):
        self.db, self.user_id = db, user_id
        with db.connect() as conn:
            if not conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
                raise ValueError("An authenticated account is required.")

    def preview(self, rows):
        """Count prospective new sessions without writing any records."""
        with self.db.connect() as conn:
            saved = {
                (start, end)
                for start, end in conn.execute(
                    "SELECT session_start, session_end FROM sleep_cycle_sessions WHERE user_id = ?",
                    (self.user_id,),
                ).fetchall()
            }
        return {
            "new": sum((r["session_start"], r["session_end"]) not in saved for r in rows),
            "duplicates": sum((r["session_start"], r["session_end"]) in saved for r in rows),
        }

    def import_sessions(self, rows):
        """Reimports safely skip exact duplicates; no personal note/location stored."""
        inserted = 0
        with self.db.connect() as conn:
            for row in rows:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO sleep_cycle_sessions
                    (user_id, session_start, session_end, night,
                     sleep_quality_pct, sleep_hours, time_in_bed_hours)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (self.user_id, row["session_start"], row["session_end"],
                     row["night"], row["sleep_quality_pct"], row["sleep_hours"],
                     row["time_in_bed_hours"]),
                )
                inserted += int(cursor.rowcount == 1)
        return {"imported": inserted, "duplicates": len(rows) - inserted}

    def history(self, start=None, end=None):
        sql = (
            "SELECT session_start, session_end, night, sleep_quality_pct, "
            "sleep_hours, time_in_bed_hours FROM sleep_cycle_sessions WHERE user_id = ?"
        )
        args = [self.user_id]
        if start is not None:
            sql += " AND night >= ?"
            args.append(start.isoformat())
        if end is not None:
            sql += " AND night <= ?"
            args.append(end.isoformat())
        sql += " ORDER BY session_end"
        with self.db.connect() as conn:
            records = conn.execute(sql, tuple(args)).fetchall()
        keys = ("session_start", "session_end", "night", "sleep_quality_pct",
                "sleep_hours", "time_in_bed_hours")
        return [dict(zip(keys, record)) for record in records]

    def delete_all(self):
        """Deliberate full dataset removal, separate from other sleep report types."""
        with self.db.connect() as conn:
            conn.execute(
                "DELETE FROM sleep_cycle_sessions WHERE user_id = ?",
                (self.user_id,),
            )
