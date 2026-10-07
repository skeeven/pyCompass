"""Validate sparse, adjacent period comparisons and the trends screen."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from test_app import open_app

from compass.trends import trend_summary


def row(day, mood=5, energy=6, stress=7):
    """Build one measured day for calendar boundary checks."""
    return dict(day=day, mood=mood, energy=energy, stress=stress)


def test_adjacent_periods_and_sparse_means():
    """Include boundaries, exclude future dates, and average measured days."""
    rows = [
        row("2026-09-22", mood=10),
        row("2026-09-23", mood=2, stress=9),
        row("2026-09-29", mood=4, stress=7),
        row("2026-09-30", mood=6, stress=5),
        row("2026-10-06", mood=10, stress=3),
        row("2026-10-07", mood=1),
    ]
    summary = trend_summary(rows, date(2026, 10, 6), 7)
    assert summary["start"] == date(2026, 9, 30)
    assert summary["previous_start"] == date(2026, 9, 23)
    assert summary["previous_end"] == date(2026, 9, 29)
    assert len(summary["current"]) == 2
    assert summary["previous_count"] == 2
    assert summary["means"]["mood"] == 8
    assert summary["changes"]["mood"] == 5
    assert summary["changes"]["stress"] == -4


def test_missing_periods_do_not_invent_comparisons():
    """Return no delta when either period is missing."""
    for rows in ([], [row("2026-10-06")], [row("2026-09-29")]):
        summary = trend_summary(rows, date(2026, 10, 6), 7)
        assert all(delta is None for delta in summary["changes"].values())
    with pytest.raises(ValueError):
        trend_summary([], date(2026, 10, 6), 0)


def test_trends_screen_filters_and_comparisons(monkeypatch, users):
    """Show owned ratings, period changes and end-date filters."""
    first, second = users
    today = datetime.now(ZoneInfo("America/Denver")).date()
    first.save_checkin(str(today), 8, 7, 3, 8, "")
    earlier = today - timedelta(days=7)
    first.save_checkin(str(earlier), 4, 3, 7, 6, "")
    second.save_checkin(str(today), 1, 1, 10, 2, "Other user")
    app = open_app(monkeypatch, first.db)
    app.session_state["user_id"] = first.user_id
    app.run()
    app.radio[0].set_value("Insights").run()
    app.selectbox[0].set_value(7).run()
    assert not app.exception
    assert app.metric[0].value == "8.0/10"
    assert app.metric[0].delta == "+4.0 points"
    assert app.metric[2].delta == "-4.0 points"
    app.date_input(key="trend_end_day").set_value(earlier).run()
    assert not app.exception
    assert app.metric[0].value == "4.0/10"
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any("Choose at least" in item.value for item in app.info)
