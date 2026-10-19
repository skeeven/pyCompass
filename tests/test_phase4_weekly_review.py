"""Phase 4 single weekly review keeps written and AI histories independent."""

from datetime import date

import pytest

from compass.health_daily import DailyHealthService
from compass.health_weekly import WeeklyHealthService
from compass.reflection import weekly_context
from compass.repository import Repository


def test_weekly_measures_include_mood_from_today_records(users):
    first, _ = users
    first.save_checkin("2026-10-12", 6, 7, 4, 7, "Check-in")
    first.save_checkin("2026-10-13", 8, 8, 2, 6.5, "Check-in")
    result = WeeklyHealthService(first.db, first.user_id).personalized_overview(
        date(2026, 10, 14), today=date(2026, 10, 14)
    )
    mood = result["current"]["measurements"]["mood"]
    assert mood == {"average": 7, "count": 2}
    assert result["current"]["measurements"]["energy"]["average"] == 7.5


def test_existing_health_reflections_and_ai_weekly_history_are_untouched(users):
    first, second = users
    health = WeeklyHealthService(first.db, first.user_id)
    health.save(date(2026, 10, 14), {
        "wins": "Made time for rest",
        "challenges": "Tired in afternoons",
        "next_step": "Walk after lunch",
    })
    first.add_insight("Old AI weekly reflection", kind="weekly")
    first.add_insight("Older observation", kind="observation")
    _ = health.personalized_overview(
        date(2026, 10, 14), today=date(2026, 10, 14)
    )
    assert health.get(date(2026, 10, 14))["wins"] == "Made time for rest"
    assert health.get(date(2026, 10, 14))["next_step"] == "Walk after lunch"
    assert len(first.rows("insights")) == 2
    assert [r["content"] for r in first.rows("insights")
            if r["kind"] == "weekly"] == ["Old AI weekly reflection"]
    assert WeeklyHealthService(second.db, second.user_id).get(
        date(2026, 10, 14)
    ) == {}
    assert second.rows("insights") == []


def test_ai_weekly_context_obeys_monday_boundaries_during_partial_week(users):
    first, _ = users
    first.save_checkin("2026-10-11", 9, 9, 2, 8, "Sunday")
    first.save_checkin("2026-10-12", 6, 5, 6, 6, "Monday")
    first.save_checkin("2026-10-14", 7, 7, 3, 7, "Wednesday")
    data = weekly_context(
        first, date(2026, 10, 14), start_day=date(2026, 10, 12)
    )
    assert data["start"] == "2026-10-12"
    assert data["end"] == "2026-10-14"
    assert [r["day"] for r in data["checkins"]] == [
        "2026-10-12", "2026-10-14"
    ]


def test_ai_context_rejects_more_than_one_calendar_week(users):
    first, _ = users
    for start, end in (
        (date(2026, 10, 1), date(2026, 10, 14)),
        (date(2026, 10, 15), date(2026, 10, 14)),
    ):
        with pytest.raises(ValueError):
            weekly_context(first, end, start_day=start)


def test_goal_and_reflection_remain_owned_when_no_today_checkins(users):
    first, second = users
    DailyHealthService(first.db, first.user_id).save(
        date(2026, 10, 13), {"energy": 6, "movement_minutes": 15}
    )
    first_health = WeeklyHealthService(first.db, first.user_id)
    first_health.save(date(2026, 10, 14), {"wins": "Moved around"})
    assert first_health.personalized_overview(
        date(2026, 10, 14), today=date(2026, 10, 14)
    )["current"]["measurements"]["movement_minutes"]["average"] == 15
    assert WeeklyHealthService(second.db, second.user_id).get(
        date(2026, 10, 14)
    ) == {}
