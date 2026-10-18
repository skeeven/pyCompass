"""Daily check-in context uses owned imported sessions without duplicating them."""

from datetime import date

from compass.health_checkin_context import (
    manual_checkin_patch, sleep_context_for_day,
)
from compass.health_daily import DailyHealthService
from compass.sleep_cycle_csv import SleepCycleCSVService


def _session(day, start, end, hours, quality):
    return {
        "night": day, "session_start": start, "session_end": end,
        "sleep_hours": hours, "sleep_quality_pct": quality,
        "time_in_bed_hours": None,
    }


def test_checkin_context_only_reads_own_same_day_sessions(users):
    first, second = users
    day = date(2026, 10, 16)
    SleepCycleCSVService(first.db, first.user_id).import_sessions([
        _session("2026-10-16", "2026-10-15 23:30:00",
                 "2026-10-16 06:30:00", 6.5, 76)
    ])
    context = sleep_context_for_day(first.db, first.user_id, day)
    assert context["sleep_hours"] == 6.5
    assert context["sleep_quality_pct"] == 76
    assert context["session_count"] == 1
    assert sleep_context_for_day(second.db, second.user_id, day)["session_count"] == 0
    assert DailyHealthService(first.db, first.user_id).get(day) == {}


def test_checkin_context_aggregates_multiple_sessions_without_overwriting():
    from compass.health_checkin_context import manual_checkin_patch
    existing = {"sleep_hours": 7.0, "notes": "private"}
    patched = manual_checkin_patch(existing, {"energy": 8, "stress": 3})
    assert patched == {"sleep_hours": 7.0, "notes": "private",
                       "energy": 8, "stress": 3}
    assert existing == {"sleep_hours": 7.0, "notes": "private"}


def test_multiple_sessions_use_duration_weighted_quality(users):
    first, _ = users
    day = date(2026, 10, 16)
    SleepCycleCSVService(first.db, first.user_id).import_sessions([
        _session("2026-10-16", "2026-10-15 23:00:00",
                 "2026-10-16 03:00:00", 4, 80),
        _session("2026-10-16", "2026-10-16 03:30:00",
                 "2026-10-16 06:30:00", 2, 50),
    ])
    context = sleep_context_for_day(first.db, first.user_id, day)
    assert context["session_count"] == 2
    assert context["sleep_hours"] == 6
    assert context["sleep_quality_pct"] == 70


def test_missing_sleep_measurements_remain_missing(users):
    first, _ = users
    day = date(2026, 10, 16)
    SleepCycleCSVService(first.db, first.user_id).import_sessions([
        _session("2026-10-16", "2026-10-15 23:00:00",
                 "2026-10-16 06:00:00", None, None),
    ])
    result = sleep_context_for_day(first.db, first.user_id, day)
    assert result["sleep_hours"] is None
    assert result["sleep_quality_pct"] is None
