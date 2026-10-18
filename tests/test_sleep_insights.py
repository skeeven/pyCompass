"""Nightly Sleep Cycle insights preserve missing values and reporting sources."""

from datetime import date

from compass.health_dashboard import dashboard_snapshot
from compass.health_reports import save_report
from compass.sleep_cycle_csv import SleepCycleCSVService
from compass.sleep_insights import sleep_cycle_insights


def session(start, end, quality=None, hours=None):
    return {
        "session_start": start, "session_end": end,
        "night": end[:10], "sleep_quality_pct": quality,
        "sleep_hours": hours, "time_in_bed_hours": None,
    }


def test_sleep_insights_windows_exclude_missing_and_future_observations():
    rows = [
        session("2026-10-12 23:00:00", "2026-10-13 06:00:00", 70, 6),
        session("2026-10-13 23:15:00", "2026-10-14 06:20:00", None, 8),
        session("2026-10-01 23:00:00", "2026-10-02 07:00:00", 40, 5),
        session("2026-10-14 23:00:00", "2026-10-15 07:00:00", 100, 9),
    ]
    output = sleep_cycle_insights(rows, date(2026, 10, 14))
    assert output["latest"]["night"] == "2026-10-14"
    assert output["as_of"] == "2026-10-14"
    assert output["windows"][7]["sessions"] == 2
    assert output["windows"][7]["averages"]["sleep_quality_pct"] == 70
    assert output["windows"][7]["counts"]["sleep_quality_pct"] == 1
    assert output["windows"][7]["averages"]["sleep_hours"] == 7
    assert output["windows"][30]["counts"]["sleep_quality_pct"] == 2


def test_adjacent_week_comparison_uses_disjoint_periods():
    rows = [
        session("2026-10-05 23:00:00", "2026-10-06 07:00:00", 60, 5),
        session("2026-10-12 23:00:00", "2026-10-13 07:00:00", 80, 7),
    ]
    result = sleep_cycle_insights(rows, date(2026, 10, 14))
    assert result["comparison"]["sleep_quality_pct"]["change"] == 20
    assert result["comparison"]["sleep_hours"]["change"] == 2
    assert result["comparison"]["sleep_quality_pct"]["current_count"] == 1


def test_midnight_wrap_does_not_average_bedtime_to_noon():
    rows = [
        session("2026-10-12 23:50:00", "2026-10-13 07:00:00", 70, 7),
        session("2026-10-14 00:10:00", "2026-10-14 07:05:00", 80, 6),
    ]
    result = sleep_cycle_insights(rows, date(2026, 10, 14))
    assert result["bedtime"]["typical"] in {"23:50", "00:10", "00:00"}
    assert result["bedtime"]["mean_deviation_minutes"] <= 20


def test_dashboard_keeps_cpap_aggregates_separate_and_is_owner_scoped(users):
    first, second = users
    records = [
        session("2026-10-12 23:00:00", "2026-10-13 06:00:00", 75, 7)
    ]
    SleepCycleCSVService(first.db, first.user_id).import_sessions(records)
    save_report(
        first.db, first.user_id, "resmed.pdf", "ResMed CPAP",
        date(2026, 9, 13), date(2026, 10, 12),
        {"ahi": 0.9, "cpap_usage_hours": 5.55},
    )
    save_report(
        first.db, first.user_id, "quality.pdf", "Sleep Cycle",
        date(2026, 10, 1), date(2026, 10, 14),
        {"sleep_quality_pct": 66}, estimated=True,
    )
    own = dashboard_snapshot(first.db, first.user_id, date(2026, 10, 14))
    other = dashboard_snapshot(second.db, second.user_id, date(2026, 10, 14))
    assert own["sleep_cycle"]["windows"][7]["averages"]["sleep_quality_pct"] == 75
    assert own["latest_cpap_report"]["metrics"]["ahi"]["value"] == 0.9
    assert own["weekly"]["days_logged"] == 0
    assert other["sleep_cycle"]["latest"] is None
    assert other["latest_cpap_report"] is None
