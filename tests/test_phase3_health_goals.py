"""Phase 3 goals: direction, explicit nutrition and source-aware observation counts."""

from datetime import date
import json

import pytest

from compass.health import HealthService
from compass.health_daily import DailyHealthService
from compass.health_goals import enriched_goal_progress, validate_goals
from compass.sleep_cycle_csv import SleepCycleCSVService
from compass.unified_sleep import unified_sleep_snapshot


def test_expanded_goals_validate_bounds_and_finite_numbers():
    assert validate_goals({
        "energy": 7, "stress": 4, "weight_lb": 205,
        "nutrition_on_track": 1
    })["weight_lb"] == 205
    for goal in (
        {"energy": 11}, {"stress": 0}, {"weight_lb": -1},
        {"nutrition_on_track": 0}, {"weight_lb": float("nan")},
        {"energy": float("inf")},
    ):
        with pytest.raises(ValueError):
            validate_goals(goal)


def test_manual_energy_stress_and_nutrition_only_count_recorded_days():
    rows = [
        {"day": "2026-10-16", "energy": 8, "stress": 3,
         "nutrition_on_track": 1},
        {"day": "2026-10-17", "energy": 5, "stress": 7,
         "nutrition_on_track": 0},
        {"day": "2026-10-15", "nutrition_note": "healthy meal"},
    ]
    progress = enriched_goal_progress(rows, [], {
        "energy": 7, "stress": 4, "nutrition_on_track": 1
    }, date(2026, 10, 17))
    assert progress["energy"]["met"] == 1
    assert progress["stress"]["met"] == 1
    assert progress["nutrition_on_track"]["met"] == 1
    assert progress["nutrition_on_track"]["recorded"] == 2


def test_weight_trajectory_and_single_reading_no_false_trend():
    rows = [{"day": "2026-10-11", "weight_lb": 230},
            {"day": "2026-10-17", "weight_lb": 227}]
    result = enriched_goal_progress(rows, [], {"weight_lb": 205},
                                     date(2026, 10, 17))
    assert result["weight_lb"]["recorded"] == 2
    assert result["weight_lb"]["change"] == -3
    assert result["weight_lb"]["remaining"] == 22
    single = enriched_goal_progress(rows[:1], [], {"weight_lb": 205},
                                    date(2026, 10, 17))
    assert single["weight_lb"]["change"] is None


def test_sleep_cycle_precedence_and_manual_fallback_in_goals():
    rows = [
        {"day": "2026-10-16", "sleep_hours": 8},
        {"day": "2026-10-17", "sleep_hours": 7},
    ]
    nights = [
        {"night": "2026-10-16", "sleep_hours": 5.5,
         "sleep_source": "Sleep Cycle"}
    ]
    progress = enriched_goal_progress(rows, nights, {"sleep_hours": 7},
                                      date(2026, 10, 17))
    assert progress["sleep_hours"]["recorded"] == 2
    assert progress["sleep_hours"]["met"] == 1
    assert progress["sleep_hours"]["mean"] == 6.25


def test_30_day_progress_does_not_use_future_or_older_days():
    rows = [
        {"day": "2026-09-16", "energy": 10},
        {"day": "2026-10-01", "energy": 8},
        {"day": "2026-10-18", "energy": 10},
    ]
    results = enriched_goal_progress(rows, [], {"energy": 7},
                                     date(2026, 10, 17), days=30)
    assert results["energy"]["recorded"] == 1


def test_nutrition_goal_private_and_recorded_without_inferred_notes(users):
    owner, stranger = users
    HealthService(owner.db, owner.user_id).save(
        {"tracked_goals": {"nutrition_on_track": 1, "energy": 7}}, 6)
    DailyHealthService(owner.db, owner.user_id).save(
        date(2026, 10, 17), {"nutrition_on_track": 0, "nutrition_note": "private"}
    )
    assert HealthService(stranger.db, stranger.user_id).load()["answers"] == {}
    assert DailyHealthService(stranger.db, stranger.user_id).history() == []
    assert DailyHealthService(owner.db, owner.user_id).get(
        date(2026, 10, 17))["nutrition_on_track"] == 0
    exported = json.loads(owner.export())
    assert len(exported["health_daily_logs"]) == 1
