"""Phase 4: original Today and Health history converge without data loss."""

from datetime import date
import json

import pytest

from compass.health_daily import DailyHealthService
from compass.repository import Repository
from compass.unified_daily import UnifiedDailyService, reconcile_daily
from compass.health_dashboard import dashboard_snapshot
from compass.health_weekly import WeeklyHealthService


def test_projection_is_nondestructive_and_carries_field_sources(users):
    owner, _ = users
    day = date(2026, 10, 14)
    owner.save_checkin(day.isoformat(), 6, 3, 4, 5, "Original", needs="quiet")
    DailyHealthService(owner.db, owner.user_id).save(
        day, {"energy": 8, "stress": 2, "sleep_hours": 7, "weight_lb": 240}
    )
    view = UnifiedDailyService(owner.db, owner.user_id).get(day)
    assert view["values"]["mood"] == 6
    assert view["values"]["energy"] == 8
    assert view["values"]["sleep_hours"] == 7
    assert view["values"]["weight_lb"] == 240
    assert view["sources"]["mood"] == "Today"
    assert view["sources"]["energy"] == "Health"
    assert view["conflicts"]["energy"] == {"today": 3, "health": 8}
    assert owner.rows("checkins")[0]["energy"] == 3
    assert DailyHealthService(owner.db, owner.user_id).get(day)["energy"] == 8


def test_today_write_is_atomic_and_preserves_other_health_values(users):
    owner, _ = users
    day = date(2026, 10, 14)
    DailyHealthService(owner.db, owner.user_id).save(
        day, {"weight_lb": 237, "movement_minutes": 20}
    )
    merged = UnifiedDailyService(owner.db, owner.user_id)
    merged.save_today(day, 8, 7, 3, 6.5, "Note", needs="rest")
    assert len(owner.rows("checkins")) == 1
    assert owner.rows("checkins")[0]["needs"] == "rest"
    health = DailyHealthService(owner.db, owner.user_id).get(day)
    assert health["energy"] == 7
    assert health["stress"] == 3
    assert health["sleep_hours"] == 6.5
    assert health["weight_lb"] == 237
    assert health["movement_minutes"] == 20
    merged.save_today(day, 9, 8, 4, 7, "Adjusted")
    assert len(owner.rows("checkins")) == 1
    assert health["weight_lb"] == DailyHealthService(owner.db, owner.user_id).get(day)["weight_lb"]


def test_health_edits_update_preexisting_today_without_inventing_mood(users):
    owner, _ = users
    day = date(2026, 10, 14)
    shared = UnifiedDailyService(owner.db, owner.user_id)
    shared.save_health(day, {"energy": 6})
    assert owner.rows("checkins") == []
    owner.save_checkin(day.isoformat(), 7, 4, 3, 6, "Original feelings")
    shared.save_health(day, {"energy": 9, "stress": 5})
    row = owner.rows("checkins")[0]
    assert row["energy"] == 9 and row["stress"] == 5
    assert row["mood"] == 7 and row["note"] == "Original feelings"
    assert shared.get(day)["conflicts"] == {}


def test_health_overview_reads_legacy_today_only_observations(users):
    owner, _ = users
    day = date(2026, 10, 14)
    owner.save_checkin(day.isoformat(), 7, 8, 3, 6.5, "Note")
    dashboard = dashboard_snapshot(owner.db, owner.user_id, day)
    assert dashboard["latest_checkin"]["energy"] == 8
    assert dashboard["weekly"]["averages"]["sleep_hours"] == 6.5
    summary = WeeklyHealthService(owner.db, owner.user_id).personalized_overview(
        day, today=day
    )
    assert summary["current"]["measurements"]["energy"]["average"] == 8


def test_other_users_and_future_days_are_excluded(users):
    first, second = users
    first.save_checkin("2026-10-14", 5, 6, 7, 8, "Private")
    assert UnifiedDailyService(second.db, second.user_id).history() == []
    assert UnifiedDailyService(first.db, first.user_id).history(
        end=date(2026, 10, 13)
    ) == []
    with pytest.raises(ValueError):
        UnifiedDailyService(first.db, first.user_id).save_today(
            date(2027, 1, 1), 5, 6, 7, 8, "future"
        )


def test_invalid_save_does_not_corrupt_original_records(users):
    owner, _ = users
    day = date(2026, 10, 14)
    shared = UnifiedDailyService(owner.db, owner.user_id)
    with pytest.raises(ValueError):
        shared.save_today(day, 5, 7, 3, float("nan"), "invalid")
    assert owner.rows("checkins") == []
    assert DailyHealthService(owner.db, owner.user_id).get(day) == {}
    with pytest.raises(ValueError):
        shared.save_health(day, {"energy": 14})
    assert shared.history() == []
