"""Check ResMed report OCR summary parsing without using private PDF fixtures."""

from datetime import date

from compass.resmed_ocr import parse_resmed_periods

RESMED_OCR_SAMPLE = """
Sleep therapy report
Sep 13, 2026 - Oct 12, 2026 (within 30 days)
Average usage 5 hours 33 minutes Days used 2 4 hours 25/29 (86.21%)
Leak 95th % 7.46 L/min Days used = 6 hours 11/29 (37.93 %)
Average AHI 0.90 events per hour
Usage hours
Jul 15, 2026 - Oct 12, 2026 (within 90 days)
Average usage 5 hours 19 minutes Days used 2 4 hours 70/89 (78.65 %)
Leak 95th % 10.12 L/min Days used = 6 hours 29/89 (32.58 %)
Average AHI 1.16 events per hour
Usage hours
Oct 13, 2025 - Oct 12, 2026 (within 365 days)
Average usage 5 hours 1 minutes Days used 2 4 hours 255/364 (70.05 %)
Leak 95th % 12.02 L/min Days used = 6 hours 99/364 (27.20 %)
Average AHI 1.08 events per hour
Usage hours
"""


def test_resmed_ocr_parser_preserves_three_separate_periods():
    periods = parse_resmed_periods(RESMED_OCR_SAMPLE)
    assert [(item["start"], item["end"]) for item in periods] == [
        (date(2026, 9, 13), date(2026, 10, 12)),
        (date(2026, 7, 15), date(2026, 10, 12)),
        (date(2025, 10, 13), date(2026, 10, 12)),
    ]
    assert [p["metrics"]["ahi"] for p in periods] == [0.90, 1.16, 1.08]
    assert [p["metrics"]["leak_l_min"] for p in periods] == [7.46, 10.12, 12.02]
    assert [p["metrics"]["nights_over_four_hours"] for p in periods] == [25, 70, 255]
    assert [p["metrics"]["nights_over_six_hours"] for p in periods] == [11, 29, 99]
    assert periods[0]["denominators"] == {
        "nights_over_four_hours": 29,
        "nights_over_six_hours": 29,
    }
    assert abs(periods[0]["metrics"]["cpap_usage_hours"] - 5.55) < 0.0001


def test_unrecognized_text_is_not_mistaken_for_report_periods():
    assert parse_resmed_periods("PDF gibberish without dates") == []
