"""Compass Health dashboard shows only owned and observed data."""

from datetime import date

from compass.health import HealthService
from compass.health_daily import DailyHealthService
from compass.health_dashboard import dashboard_snapshot
from compass.health_reports import save_report
from compass.health_weekly import WeeklyHealthService


def test_dashboard_empty_state_and_account_isolation(users):
    first, second = users
    day = date(2026, 10, 14)
    DailyHealthService(first.db, first.user_id).save(
        day, {"sleep_hours": 6.5, "energy": 6}
    )
    HealthService(first.db, first.user_id).save({"goals": "Walk daily"}, 6)
    own = dashboard_snapshot(first.db, first.user_id, day)
    other = dashboard_snapshot(second.db, second.user_id, day)
    assert own["latest_checkin"]["sleep_hours"] == 6.5
    assert own["profile"]["answers"]["goals"] == "Walk daily"
    assert other["latest_checkin"] is None
    assert other["profile"]["answers"] == {}
    assert other["latest_report"] is None
    assert other["weekly"]["days_logged"] == 0


def test_dashboard_separates_aggregated_report_from_daily_readings(users):
    first, _ = users
    day = date(2026, 10, 14)
    daily = DailyHealthService(first.db, first.user_id)
    daily.save(date(2026, 10, 13), {"sleep_hours": 6})
    save_report(
        first.db, first.user_id, "resmed.pdf", "ResMed CPAP",
        date(2026, 9, 13), date(2026, 10, 12),
        {"cpap_usage_hours": 5.55, "ahi": 0.9},
    )
    WeeklyHealthService(first.db, first.user_id).save(
        day, {"next_step": "Walk after lunch"}
    )
    snap = dashboard_snapshot(first.db, first.user_id, day)
    assert snap["weekly"]["averages"]["sleep_hours"] == 6
    assert "cpap_hours" not in snap["weekly"]["averages"]
    assert snap["latest_report"]["metrics"]["ahi"]["value"] == 0.9
    assert snap["reflection"]["next_step"] == "Walk after lunch"


def test_dashboard_does_not_present_old_checkin_as_recent(users):
    first, _ = users
    daily = DailyHealthService(first.db, first.user_id)
    daily.save(date(2026, 10, 1), {"energy": 4})
    snap = dashboard_snapshot(first.db, first.user_id, date(2026, 10, 14))
    assert snap["latest_checkin"] is None
    assert snap["weekly"]["days_logged"] == 0
