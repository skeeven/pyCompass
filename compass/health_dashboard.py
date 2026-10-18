"""Owner-scoped summary for the Compass Health landing dashboard."""

from datetime import timedelta

from compass.health import HealthService
from compass.health_daily import DailyHealthService, weekly_summary
from compass.health_history import list_saved_reports
from compass.health_weekly import WeeklyHealthService
from compass.sleep_cycle_csv import SleepCycleCSVService
from compass.sleep_insights import sleep_cycle_insights
from compass.unified_sleep import unified_sleep_snapshot
from compass.health_patterns import personalized_health_insights


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
    cpap_reports = [r for r in reports if r["report_type"] == "ResMed CPAP"]
    cpap_reports.sort(
        key=lambda report: (report["period_end"], report["uploaded_at"]),
        reverse=True,
    )
    reports.sort(
        key=lambda report: (report["period_end"], report["uploaded_at"]),
        reverse=True,
    )
    cycle_sessions = SleepCycleCSVService(db, user_id).history(
        start=today - timedelta(days=89), end=today
    )
    unified = unified_sleep_snapshot(history, cycle_sessions, reports, today)
    return {
        "latest_checkin": current,
        "weekly": weekly,
        "profile": profile,
        "reflection": weekly_review,
        "latest_report": reports[0] if reports else None,
        "latest_cpap_report": cpap_reports[0] if cpap_reports else None,
        "sleep_cycle": sleep_cycle_insights(cycle_sessions, today),
        "unified_sleep": unified,
        "personalized_insights": personalized_health_insights(history, unified, today),
    }
