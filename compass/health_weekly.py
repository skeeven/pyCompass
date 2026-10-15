"""Private weekly Compass Health reflections with current-source summaries."""

import json
from datetime import date, timedelta

from compass.health_daily import DailyHealthService, weekly_summary
from compass.health_history import list_saved_reports

FIELDS = ("wins", "challenges", "next_step")


def week_bounds(day):
    """Use Monday through Sunday, including partial current weeks."""
    if not isinstance(day, date):
        raise ValueError("Select a valid week date.")
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


class WeeklyHealthService:
    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id
        self.daily = DailyHealthService(db, user_id)

    def overview(self, day, today=None):
        """Compute a fresh summary from logged days, never PDF aggregates."""
        start, end = week_bounds(day)
        if today is not None and end > today:
            end = today
        if end < start:
            raise ValueError("Week hasn't started.")
        rows = self.daily.history(start, end)
        summary = weekly_summary(rows, end) if (end - start).days == 6 else {
            "start": start, "end": end, "days_logged": len(rows),
            "averages": {
                key: sum(row[key] for row in rows if key in row)
                / len([row for row in rows if key in row])
                for key in ("sleep_hours", "cpap_hours", "energy", "stress",
                            "hunger", "weight_lb", "waist_in",
                            "movement_minutes", "downtime_minutes")
                if any(key in row for row in rows)
            },
        }
        summary["measurement_counts"] = {
            key: sum(key in row for row in rows)
            for key in summary["averages"]
        }
        # Reports are supplied only as separate context, never averaged with logs.
        summary["reports"] = [
            {"period_start": r["period_start"], "period_end": r["period_end"],
             "source": r["report_type"]}
            for r in list_saved_reports(self.db, self.user_id)
            if r["period_end"] >= start.isoformat()
            and r["period_start"] <= end.isoformat()
        ]
        return summary

    def get(self, day):
        start, _ = week_bounds(day)
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT review_json FROM health_weekly_reviews "
                "WHERE user_id = ? AND week_start = ?",
                (self.user_id, start.isoformat()),
            ).fetchone()
        return json.loads(row[0]) if row else {}

    def save(self, day, answers):
        start, _ = week_bounds(day)
        if start > date.today():
            raise ValueError("Cannot review a future week.")
        if not isinstance(answers, dict) or set(answers) - set(FIELDS):
            raise ValueError("Unknown review field.")
        for key, value in answers.items():
            if not isinstance(value, str) or len(value) > 2000:
                raise ValueError(f"Invalid review text: {key}.")
        data = json.dumps({key: value.strip() for key, value in answers.items()})
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO health_weekly_reviews
                   (user_id, week_start, review_json) VALUES (?, ?, ?)
                   ON CONFLICT(user_id, week_start)
                   DO UPDATE SET review_json = excluded.review_json""",
                (self.user_id, start.isoformat(), data),
            )

    def history(self):
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT week_start, review_json FROM health_weekly_reviews "
                "WHERE user_id = ? ORDER BY week_start DESC",
                (self.user_id,),
            ).fetchall()
        return [{"week_start": day, **json.loads(value)} for day, value in rows]
