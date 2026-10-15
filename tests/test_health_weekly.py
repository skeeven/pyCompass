"""Weekly health reviews remain private, editable, and non-diagnostic."""

from datetime import date

import pytest

from compass.health_daily import DailyHealthService
from compass.health_reports import save_report
from compass.health_weekly import WeeklyHealthService, week_bounds


def test_week_bounds_are_monday_through_sunday():
    assert week_bounds(date(2026, 10, 14)) == (
        date(2026, 10, 12), date(2026, 10, 18)
    )


def test_weekly_review_is_saved_and_owner_scoped(users):
    first, second = users
    a = WeeklyHealthService(first.db, first.user_id)
    b = WeeklyHealthService(second.db, second.user_id)
    day = date(2026, 10, 12)
    assert b.get(day) == {}
    a.save(day, {"wins": "Walked twice", "next_step": "Go to bed earlier"})
    assert a.get(day)["wins"] == "Walked twice"
    assert b.get(day) == {}
    assert b.history() == []
    a.save(day, {"wins": "Walked three times"})
    assert a.get(day) == {"wins": "Walked three times"}
    assert len(a.history()) == 1


def test_weekly_summary_uses_actual_daily_values_and_keeps_pdf_separate(users):
    first, _ = users
    daily = DailyHealthService(first.db, first.user_id)
    weekly = WeeklyHealthService(first.db, first.user_id)
    daily.save(date(2026, 10, 12), {"energy": 4, "sleep_hours": 6})
    daily.save(date(2026, 10, 13), {"energy": 8})
    save_report(
        first.db, first.user_id, "report.pdf", "ResMed CPAP",
        date(2026, 9, 13), date(2026, 10, 12),
        {"cpap_usage_hours": 5.55},
    )
    result = weekly.overview(date(2026, 10, 14), today=date(2026, 10, 14))
    assert result["days_logged"] == 2
    assert result["averages"]["energy"] == 6
    assert result["averages"]["sleep_hours"] == 6
    assert result["measurement_counts"]["sleep_hours"] == 1
    assert "cpap_hours" not in result["averages"]
    assert len(result["reports"]) == 1


def test_weekly_review_validation(users):
    first, _ = users
    weekly = WeeklyHealthService(first.db, first.user_id)
    with pytest.raises(ValueError):
        weekly.save(date(2026, 10, 12), {"diagnosis": "X"})
    with pytest.raises(ValueError):
        weekly.save(date(2026, 10, 12), {"wins": "x" * 2001})


def test_weekly_review_export_and_account_delete(users):
    import json

    first, second = users
    WeeklyHealthService(first.db, first.user_id).save(
        date(2026, 10, 12), {"wins": "Rested"}
    )
    assert len(json.loads(first.export())["health_weekly_reviews"]) == 1
    assert json.loads(second.export())["health_weekly_reviews"] == []
    first.delete_account()
    with first.db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM health_weekly_reviews WHERE user_id = ?",
            (first.user_id,),
        ).fetchone()[0] == 0
