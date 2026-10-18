"""Personalized weekly review is grounded in recorded, owner-scoped data."""

from datetime import date

import pytest

from compass.health import HealthService
from compass.health_daily import DailyHealthService
from compass.health_reports import save_report
from compass.health_weekly import WeeklyHealthService
from compass.sleep_cycle_csv import SleepCycleCSVService


def session(day, hours, quality, start=None):
    return {
        "night": day,
        "session_start": start or f"{day} 00:00:00",
        "session_end": f"{day} 07:00:00",
        "sleep_hours": hours,
        "sleep_quality_pct": quality,
        "time_in_bed_hours": 8.0,
    }


def test_partial_week_only_includes_monday_onward(users):
    first, _ = users
    daily = DailyHealthService(first.db, first.user_id)
    daily.save(date(2026, 10, 11), {"energy": 10, "movement_minutes": 100})
    daily.save(date(2026, 10, 12), {"energy": 4, "movement_minutes": 15})
    result = WeeklyHealthService(first.db, first.user_id).personalized_overview(
        date(2026, 10, 14), today=date(2026, 10, 14)
    )
    assert result["start"] == date(2026, 10, 12)
    assert result["end"] == date(2026, 10, 14)
    assert result["current"]["checkin_days"] == 1
    assert result["current"]["measurements"]["energy"]["average"] == 4
    assert result["previous"]["measurements"]["energy"]["average"] == 10
    assert result["changes"] == {}


def test_sleep_cycle_replaces_manual_sleep_without_double_counting(users):
    first, _ = users
    daily = DailyHealthService(first.db, first.user_id)
    daily.save(date(2026, 10, 12), {"sleep_hours": 9, "energy": 7})
    daily.save(date(2026, 10, 13), {"sleep_hours": 7, "energy": 8})
    SleepCycleCSVService(first.db, first.user_id).import_sessions([
        session("2026-10-12", 6, 75)
    ])
    HealthService(first.db, first.user_id).save(
        {"tracked_goals": {"sleep_hours": 7, "energy": 7}}, 6
    )
    report = WeeklyHealthService(first.db, first.user_id).personalized_overview(
        date(2026, 10, 14), today=date(2026, 10, 14)
    )
    sleep = report["current"]["measurements"]["sleep_hours"]
    assert sleep["count"] == 2
    assert sleep["average"] == 6.5
    assert report["goals"]["sleep_hours"]["met"] == 1
    assert report["goals"]["sleep_hours"]["recorded"] == 2
    assert report["current"]["measurements"]["sleep_quality_pct"]["average"] == 75


def test_previous_week_change_requires_two_observations_each(users):
    first, _ = users
    daily = DailyHealthService(first.db, first.user_id)
    for day, energy in ((5, 4), (6, 6), (12, 7), (13, 9)):
        daily.save(date(2026, 10, day), {"energy": energy})
    result = WeeklyHealthService(first.db, first.user_id).personalized_overview(
        date(2026, 10, 14), today=date(2026, 10, 14)
    )
    assert result["changes"]["energy"]["difference"] == 3
    assert result["changes"]["energy"]["current_count"] == 2
    assert result["changes"]["energy"]["previous_count"] == 2


def test_resmed_overlapping_reports_are_context_only(users):
    first, _ = users
    save_report(first.db, first.user_id, "cpap.pdf", "ResMed CPAP",
                date(2026, 9, 13), date(2026, 10, 12),
                {"cpap_usage_hours": 5.55, "ahi": 0.9})
    summary = WeeklyHealthService(first.db, first.user_id).personalized_overview(
        date(2026, 10, 14), today=date(2026, 10, 14)
    )
    assert summary["current"]["measurements"] == {}
    assert len(summary["report_context"]) == 1
    assert summary["report_context"][0]["source"] == "ResMed CPAP"


def test_private_account_only_sees_owned_weekly_data(users):
    first, second = users
    DailyHealthService(first.db, first.user_id).save(
        date(2026, 10, 14), {"stress": 4}
    )
    own = WeeklyHealthService(first.db, first.user_id).personalized_overview(
        date(2026, 10, 14), today=date(2026, 10, 14)
    )
    other = WeeklyHealthService(second.db, second.user_id).personalized_overview(
        date(2026, 10, 14), today=date(2026, 10, 14)
    )
    assert own["current"]["measurements"]["stress"]["average"] == 4
    assert other["current"]["checkin_days"] == 0
    assert other["current"]["measurements"] == {}
    assert other["goals"] == {}


def test_future_week_cannot_be_reviewed(users):
    first, _ = users
    with pytest.raises(ValueError, match="hasn't started"):
        WeeklyHealthService(first.db, first.user_id).personalized_overview(
            date(2026, 10, 26), today=date(2026, 10, 14)
        )
