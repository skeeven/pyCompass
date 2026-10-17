"""Owner-scoped summary for the Compass Health landing dashboard."""

from datetime import timedelta

from compass.health import HealthService
from compass.health_daily import DailyHealthService, weekly_summary
from compass.health_history import list_saved_reports
from compass.health_weekly import WeeklyHealthService


def dashboard_snapshot(db, user_id, today):
    """Only use the authenticated account's data and observed measurements."""
    daily = DailyHealthService(db, user_id)
    history = daily.history(end=today)
    recent = [row for row in history if row["day"] >=
              (today - timedelta(days=6)).isoformat()]
    current = recent[-1] if recent else None
    weekly = weekly_summary(recent, today)
    profile = HealthService(db, user_id).load()
    weekly_review = WeeklyHealthService(db, user_id).get(today)
    reports = [
        report for report in list_saved_reports(db, user_id)
        if report["status"] == "verified" and report["period_end"] <= today.isoformat()
    ]
    reports.sort(
        key=lambda report: (report["period_end"], report["uploaded_at"]),
        reverse=True,
    )
    return {
        "latest_checkin": current,
        "weekly": weekly,
        "profile": profile,
        "reflection": weekly_review,
        "latest_report": reports[0] if reports else None,
    }
