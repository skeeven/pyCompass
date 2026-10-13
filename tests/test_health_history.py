"""Health report history is persisted and isolated per account."""

from datetime import date

from compass.health_history import list_saved_reports
from compass.health_reports import save_report


def test_saved_health_report_history_is_owner_scoped(users):
    first, second = users
    rid = save_report(
        first.db, first.user_id, "resmed-report.pdf", "ResMed CPAP",
        date(2026, 9, 13), date(2026, 10, 12),
        {"ahi": 0.9, "cpap_usage_hours": 5.55, "nights_over_four_hours": 25},
        {"nights_over_four_hours": 29},
    )
    assert list_saved_reports(first.db, second.user_id) == []
    saved = list_saved_reports(first.db, first.user_id)
    assert len(saved) == 1
    assert saved[0]["id"] == rid
    assert saved[0]["period_start"] == "2026-09-13"
    assert saved[0]["period_end"] == "2026-10-12"
    assert saved[0]["metrics"]["ahi"]["value"] == 0.9
    assert saved[0]["metrics"]["nights_over_four_hours"]["source"].endswith("25/29 nights")


def test_history_preserves_multiple_periods(users):
    first, _ = users
    for start, ahi in [(date(2026, 9, 13), 0.90), (date(2026, 7, 15), 1.16)]:
        save_report(
            first.db, first.user_id, "same-report.pdf", "ResMed CPAP",
            start, date(2026, 10, 12), {"ahi": ahi},
        )
    history = list_saved_reports(first.db, first.user_id)
    assert len(history) == 2
    assert {r["metrics"]["ahi"]["value"] for r in history} == {0.90, 1.16}
