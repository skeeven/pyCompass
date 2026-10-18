"""Matched-day wellness insights avoid invented measurements and leakage."""

from datetime import date, timedelta

from compass.health_patterns import personalized_health_insights, pearson_r
from compass.health_dashboard import dashboard_snapshot
from compass.health_daily import DailyHealthService
from compass.sleep_cycle_csv import SleepCycleCSVService
from compass.unified_sleep import unified_sleep_snapshot


def _night(day, duration, quality):
    return {
        "night": day,
        "session_start": f"{day} 00:00:00",
        "session_end": f"{day} 07:00:00",
        "sleep_hours": duration,
        "sleep_quality_pct": quality,
        "time_in_bed_hours": 8.0,
    }


def test_insights_need_ten_same_day_pairs_not_just_sleep_history():
    today = date(2026, 10, 17)
    sessions = [_night((today - timedelta(days=n)).isoformat(), 6 + n / 10, 70 + n)
                for n in range(25)]
    daily = [{"day": (today - timedelta(days=n)).isoformat(), "energy": 5 + n % 2}
             for n in range(5)]
    unified = unified_sleep_snapshot(daily, sessions, [], today)
    result = personalized_health_insights(daily, unified, today)
    pair = result["patterns"][0]
    assert result["sleep_nights"] == 25
    assert pair["matched_days"] == 5
    assert pair["finding"] is None


def test_insights_respect_recorded_dates_and_quality_source():
    today = date(2026, 10, 17)
    sessions = [_night((today - timedelta(days=n)).isoformat(), 6 + n / 10, 60 + n)
                for n in range(12)]
    manual = [
        {"day": (today - timedelta(days=n)).isoformat(),
         "energy": n % 8 + 1, "stress": 9 - n % 8}
        for n in range(12)
    ]
    unified = unified_sleep_snapshot(manual, sessions, [], today)
    result = personalized_health_insights(manual, unified, today)
    assert all(item["matched_days"] == 12 for item in result["patterns"])
    assert all(item["correlation"] is not None for item in result["patterns"])
    assert all(abs(item["correlation"]) <= 1 for item in result["patterns"])


def test_constant_values_and_short_samples_produce_no_claim():
    assert pearson_r([(2, 8)] * 20) is None
    assert pearson_r([(i, i * 2) for i in range(9)]) is None
    assert pearson_r([(i, i * 2) for i in range(10)]) == 1


def test_missing_sleep_quality_never_uses_energy_or_cpap_as_proxy():
    today = date(2026, 10, 17)
    logs = [{"day": (today - timedelta(days=i)).isoformat(),
             "sleep_hours": 6 + i / 10, "energy": (i % 8) + 1}
            for i in range(12)]
    unified = unified_sleep_snapshot(logs, [], [], today)
    results = personalized_health_insights(logs, unified, today)
    assert results["patterns"][0]["matched_days"] == 12
    assert results["patterns"][2]["matched_days"] == 0


def test_insights_dashboard_is_owner_scoped(users):
    first, other = users
    today = date(2026, 10, 17)
    DailyHealthService(first.db, first.user_id).save(
        today, {"sleep_hours": 7, "energy": 6}
    )
    SleepCycleCSVService(first.db, first.user_id).import_sessions(
        [_night("2026-10-17", 6.5, 77)]
    )
    first_snapshot = dashboard_snapshot(first.db, first.user_id, today)
    other_snapshot = dashboard_snapshot(other.db, other.user_id, today)
    assert first_snapshot["personalized_insights"]["checkin_days"] == 1
    assert first_snapshot["personalized_insights"]["sleep_nights"] == 1
    assert other_snapshot["personalized_insights"]["checkin_days"] == 0
    assert other_snapshot["personalized_insights"]["sleep_nights"] == 0
