"""Goal progress, cross-week comparisons, and profile ownership."""

from datetime import date

import pytest

from compass.health import HealthService
from compass.health_daily import DailyHealthService
from compass.health_goals import compare_weeks, goal_progress, validate_goals


def test_goal_progress_counts_recorded_days_only():
    rows = [
        {"day": "2026-10-12", "sleep_hours": 7, "movement_minutes": 10},
        {"day": "2026-10-13", "sleep_hours": 5},
        {"day": "2026-10-14", "movement_minutes": 15},
    ]
    result = goal_progress(
        rows, {"sleep_hours": 6, "movement_minutes": 15},
        date(2026, 10, 14),
    )
    assert result["sleep_hours"] == {"target": 6.0, "met": 1, "recorded": 2}
    assert result["movement_minutes"] == {
        "target": 15.0, "met": 1, "recorded": 2
    }


def test_explicit_goal_validation():
    with pytest.raises(ValueError):
        validate_goals({"sleep_hours": -3})
    with pytest.raises(ValueError):
        validate_goals({"sleep_hours": True})
    with pytest.raises(ValueError):
        validate_goals({"random": 5})


def test_week_comparison_respects_samples():
    rows = [
        {"day": "2026-10-04", "energy": 4},
        {"day": "2026-10-11", "energy": 6},
        {"day": "2026-10-12", "energy": 8},
        {"day": "2026-10-13", "sleep_hours": 7},
    ]
    result = compare_weeks(rows, date(2026, 10, 14))
    assert result["comparisons"]["energy"]["previous"] == 5
    assert result["comparisons"]["energy"]["current"] == 8
    assert result["comparisons"]["energy"]["current_count"] == 1
    assert "sleep_hours" not in result["comparisons"]


def test_saved_goals_are_private_and_exportable(users):
    first, second = users
    one = HealthService(first.db, first.user_id)
    two = HealthService(second.db, second.user_id)
    one.save({"tracked_goals": {"movement_minutes": 15}}, 6)
    assert one.load()["answers"]["tracked_goals"]["movement_minutes"] == 15
    assert two.load()["answers"] == {}
    with pytest.raises(ValueError):
        one.save({"tracked_goals": {"movement_minutes": -1}}, 6)
    import json

    assert json.loads(first.export())["health_profiles"][0]["user_id"] == first.user_id


def test_quick_entry_merges_existing_measurements(users):
    first, _ = users
    daily = DailyHealthService(first.db, first.user_id)
    day = date(2026, 10, 14)
    daily.save(day, {"weight_lb": 240, "sleep_hours": 5})
    daily.save(day, {**daily.get(day), **{"sleep_hours": 7}})
    assert daily.get(day) == {"weight_lb": 240, "sleep_hours": 7}
