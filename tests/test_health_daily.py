"""Daily Compass Health log privacy, updates, validation and summaries."""

from datetime import date

import pytest

from compass.health_daily import DailyHealthService, weekly_summary


def test_daily_health_upsert_and_isolation(users):
    first, second = users
    one = DailyHealthService(first.db, first.user_id)
    two = DailyHealthService(second.db, second.user_id)
    day = date(2026, 10, 10)
    one.save(day, {"sleep_hours": 6.5, "energy": 4, "notes": "Tired"})
    assert two.get(day) == {}
    assert two.history() == []
    assert one.get(day)["sleep_hours"] == 6.5
    one.save(day, {"sleep_hours": 7.25, "movement_minutes": 15})
    assert one.get(day) == {"sleep_hours": 7.25, "movement_minutes": 15}
    assert len(one.history()) == 1
    two.save(day, {"sleep_hours": 8})
    one.delete(day)
    assert one.get(day) == {}
    assert two.get(day)["sleep_hours"] == 8


def test_missing_values_are_not_zero(users):
    first, _ = users
    service = DailyHealthService(first.db, first.user_id)
    service.save(date(2026, 10, 9), {"energy": 4})
    service.save(date(2026, 10, 10), {"energy": 8, "sleep_hours": 6.5})
    summary = weekly_summary(
        service.history(), date(2026, 10, 10)
    )
    assert summary["days_logged"] == 2
    assert summary["averages"]["energy"] == 6
    assert summary["averages"]["sleep_hours"] == 6.5
    assert "weight_lb" not in summary["averages"]


def test_daily_health_rejects_invalid_measurements(users):
    first, _ = users
    service = DailyHealthService(first.db, first.user_id)
    day = date(2026, 10, 10)
    for value in (-1, float("nan"), 30):
        with pytest.raises(ValueError):
            service.save(day, {"sleep_hours": value})
    with pytest.raises(ValueError):
        service.save(day, {"medical_diagnosis": "X"})
    with pytest.raises(ValueError):
        service.save(day, {"notes": "x" * 2001})
    assert service.get(day) == {}


def test_health_daily_export_and_account_deletion(users):
    import json

    first, second = users
    DailyHealthService(first.db, first.user_id).save(
        date(2026, 10, 10), {"weight_lb": 235.5}
    )
    exported = json.loads(first.export())
    assert len(exported["health_daily_logs"]) == 1
    assert json.loads(second.export())["health_daily_logs"] == []
    first.delete_account()
    with first.db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM health_daily_logs WHERE user_id = ?",
            (first.user_id,),
        ).fetchone()[0] == 0
