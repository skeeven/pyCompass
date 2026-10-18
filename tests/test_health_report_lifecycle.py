"""Imported report lifecycle and OCR fallback safety."""

from datetime import date

import fitz
import pytest

from compass.health_history import delete_saved_report, list_saved_reports
from compass.health_reports import save_report
from compass.sleep_cycle_ocr import recognize_sleep_cycle_pdf


def test_same_owner_source_and_period_rejected(users):
    first, second = users
    start, end = date(2026, 9, 13), date(2026, 10, 12)
    save_report(first.db, first.user_id, "first.pdf", "ResMed CPAP",
                start, end, {"ahi": 0.9})
    with pytest.raises(ValueError, match="already saved"):
        save_report(first.db, first.user_id, "second.pdf", "ResMed CPAP",
                    start, end, {"ahi": 1.1})
    # Another report source and another account have distinct records.
    save_report(first.db, first.user_id, "sleep.pdf", "Sleep Cycle",
                start, end, {"sleep_hours": 7})
    save_report(second.db, second.user_id, "report.pdf", "ResMed CPAP",
                start, end, {"ahi": 1.1})
    assert len(list_saved_reports(first.db, first.user_id)) == 2
    assert len(list_saved_reports(second.db, second.user_id)) == 1


def test_deletion_requires_owner_and_removes_all_metrics(users):
    first, second = users
    start, end = date(2026, 9, 13), date(2026, 10, 12)
    report_id = save_report(first.db, first.user_id, "private.pdf",
                            "ResMed CPAP", start, end,
                            {"ahi": 0.9, "cpap_usage_hours": 5.5})
    with pytest.raises(ValueError, match="unavailable"):
        delete_saved_report(second.db, second.user_id, report_id)
    assert len(list_saved_reports(first.db, first.user_id)[0]["metrics"]) == 2
    delete_saved_report(first.db, first.user_id, report_id)
    assert list_saved_reports(first.db, first.user_id) == []
    with first.db.connect() as conn:
        assert not conn.execute(
            "SELECT id FROM health_report_metrics WHERE report_id = ?",
            (report_id,),
        ).fetchall()
    with pytest.raises(ValueError, match="unavailable"):
        delete_saved_report(first.db, first.user_id, report_id)
    # Deleted date range can be imported again.
    save_report(first.db, first.user_id, "replacement.pdf", "ResMed CPAP",
                start, end, {"ahi": 0.8})


def test_sleep_cycle_ocr_limits_pages_and_empty_input():
    with pytest.raises(ValueError, match="non-empty"):
        recognize_sleep_cycle_pdf(b"")
    doc = fitz.open()
    for _ in range(31):
        doc.new_page()
    data = doc.tobytes()
    doc.close()
    with pytest.raises(ValueError, match="1–30"):
        recognize_sleep_cycle_pdf(data)


def test_sleep_cycle_ocr_limits_rendered_page_size():
    doc = fitz.open()
    doc.new_page(width=2500, height=2500)
    data = doc.tobytes()
    doc.close()
    with pytest.raises(ValueError, match="too large"):
        recognize_sleep_cycle_pdf(data)
