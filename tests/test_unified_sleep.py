"""Unified Sleep Health uses a consistent priority without conflating time scales."""

from datetime import date

from compass.unified_sleep import unified_sleep_snapshot
from compass.health_dashboard import dashboard_snapshot
from compass.health_daily import DailyHealthService
from compass.health_reports import save_report
from compass.sleep_cycle_csv import SleepCycleCSVService


def cycle_row(day, hours, quality):
    return {
        "night": day,
        "session_start": f"{day} 00:00:00",
        "session_end": f"{day} 07:00:00",
        "sleep_hours": hours,
        "sleep_quality_pct": quality,
        "time_in_bed_hours": None,
    }


def test_sleep_cycle_priority_manual_gap_filling_and_no_double_count():
    result = unified_sleep_snapshot(
        [{"day": "2026-10-16", "sleep_hours": 8},
         {"day": "2026-10-17", "sleep_hours": 7}],
        [cycle_row("2026-10-16", 6.5, 71)],
        [], date(2026, 10, 17),
    )
    assert result["windows"][7]["nights"] == 2
    assert result["windows"][7]["sleep_hours"] == 6.75
    assert result["windows"][7]["sleep_count"] == 2
    assert result["windows"][7]["quality_pct"] == 71
    assert result["windows"][7]["cycle_nights"] == 1
    assert result["windows"][7]["manual_nights"] == 1
    assert result["latest"]["sleep_source"] == "Manual check-in"
    assert result["nights"][0]["sleep_hours"] == 6.5


def test_missing_cycle_duration_does_not_erase_manually_logged_sleep():
    result = unified_sleep_snapshot(
        [{"day": "2026-10-16", "sleep_hours": 7}],
        [cycle_row("2026-10-16", None, 80)],
        [], date(2026, 10, 17),
    )
    assert result["latest"]["sleep_hours"] == 7
    assert result["latest"]["sleep_source"] == "Manual check-in"
    assert result["latest"]["sleep_quality_pct"] == 80


def test_latest_resmed_end_date_uses_shortest_period_as_primary(users):
    owner, _ = users
    for start, usage in (
        (date(2025, 10, 13), 5.02),
        (date(2026, 7, 15), 5.32),
        (date(2026, 9, 13), 5.55),
    ):
        save_report(owner.db, owner.user_id, "resmed.pdf", "ResMed CPAP",
                    start, date(2026, 10, 12),
                    {"cpap_usage_hours": usage, "ahi": 0.9})
    snap = dashboard_snapshot(owner.db, owner.user_id, date(2026, 10, 17))
    reports = snap["unified_sleep"]["cpap_reports"]
    assert len(reports) == 3
    assert [r["metrics"]["cpap_usage_hours"]["value"] for r in reports] == [
        5.55, 5.32, 5.02
    ]


def test_unified_dashboard_owner_isolation_and_missing_nights(users):
    owner, other = users
    DailyHealthService(owner.db, owner.user_id).save(
        date(2026, 10, 17), {"sleep_hours": 7}
    )
    SleepCycleCSVService(owner.db, owner.user_id).import_sessions([
        cycle_row("2026-10-16", 6.2, 72)
    ])
    own = dashboard_snapshot(owner.db, owner.user_id, date(2026, 10, 17))
    stranger = dashboard_snapshot(other.db, other.user_id, date(2026, 10, 17))
    assert own["unified_sleep"]["windows"][7]["sleep_count"] == 2
    assert stranger["unified_sleep"]["latest"] is None
    assert stranger["unified_sleep"]["cpap_reports"] == []
    assert stranger["unified_sleep"]["windows"][7]["sleep_hours"] is None
