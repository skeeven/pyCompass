"""Presentation-only sleep report formatting regression checks."""

from compass.health_report_display import (
    duplicate_import_message,
    format_duration,
    format_report_value,
)


def test_decimal_usage_hours_render_as_hours_and_minutes():
    assert format_duration(5.55) == "5h 33m"
    assert format_duration(5.32) == "5h 19m"
    assert format_duration(5.02) == "5h 01m"
    assert format_duration(0) == "0h 00m"


def test_saved_report_formatting_keeps_counts_whole():
    assert format_report_value("cpap_usage_hours", 5.55) == "5h 33m"
    assert format_report_value("nights_over_four_hours", 25, 29) == "25 of 29 nights"
    assert format_report_value("nights_over_six_hours", 11) == "11"
    assert format_report_value("ahi", 0.9) == "0.90"
    assert format_report_value("leak_l_min", 7.46) == "7.46"


def test_duplicate_status_is_friendly_and_no_change_claim_is_correct():
    assert duplicate_import_message(0, 3) == (
        "All 3 reporting periods already saved. No changes needed."
    )
    assert duplicate_import_message(1, 2) == (
        "1 new reporting period saved. 2 already saved; left unchanged."
    )
    assert duplicate_import_message(3, 0) == "3 new reporting periods saved."
