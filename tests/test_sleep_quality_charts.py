"""Sleep Cycle chart import accepts image/PDF exports without inventing values."""

from datetime import date
from io import BytesIO

import fitz
from PIL import Image
import pytest

from compass.health_reports import save_report
from compass.health_history import list_saved_reports
from compass.sleep_quality_charts import sleep_quality_chart_preview


@pytest.mark.parametrize("format_name,extension", [("JPEG","jpeg"),("PNG","png")])
def test_sleep_quality_chart_image_preview(format_name, extension):
    image = Image.new("RGB", (250, 180), "black")
    out = BytesIO()
    image.save(out, format=format_name)
    data = out.getvalue()
    assert sleep_quality_chart_preview(data, f"chart.{extension}") == data


def test_sleep_quality_chart_pdf_preview():
    doc = fitz.open()
    doc.new_page(width=520, height=400)
    data = doc.tobytes()
    doc.close()
    result = sleep_quality_chart_preview(data, "chart.pdf")
    with Image.open(BytesIO(result)) as image:
        assert image.format == "PNG"


def test_sleep_quality_chart_invalid_and_oversized_rejected():
    with pytest.raises(ValueError):
        sleep_quality_chart_preview(b"bad", "chart.jpg")
    with pytest.raises(ValueError, match="8 MB"):
        sleep_quality_chart_preview(b"a" * (8 * 1024 * 1024 + 1), "chart.png")
    with pytest.raises(ValueError):
        sleep_quality_chart_preview(b"bad", "chart.gif")


def test_sleep_quality_percentage_saved_as_distinct_metric_and_source(users):
    first, second = users
    report_id = save_report(
        first.db, first.user_id, "my-identity.jpg", "Sleep Cycle",
        date(2026, 9, 13), date(2026, 10, 12),
        {"sleep_quality_pct": 69.5}, estimated=True,
    )
    reports = list_saved_reports(first.db, first.user_id)
    assert reports[0]["id"] == report_id
    assert reports[0]["filename"] == "Sleep Cycle quality chart"
    assert reports[0]["metrics"]["sleep_quality_pct"]["value"] == 69.5
    assert "estimated" in reports[0]["metrics"]["sleep_quality_pct"]["source"]
    assert list_saved_reports(second.db, second.user_id) == []
    with pytest.raises(ValueError, match="already saved"):
        save_report(first.db, first.user_id, "again.pdf", "Sleep Cycle",
                    date(2026, 9, 13), date(2026, 10, 12),
                    {"sleep_quality_pct": 60})


@pytest.mark.parametrize("value", [-1, 101])
def test_sleep_quality_percent_invalid(users, value):
    first, _ = users
    with pytest.raises(ValueError, match="0 to 100"):
        save_report(
            first.db, first.user_id, "chart.jpg", "Sleep Cycle",
            date(2026, 9, 13), date(2026, 10, 12),
            {"sleep_quality_pct": value},
        )


def test_quality_metric_not_allowed_for_resmed(users):
    first, _ = users
    with pytest.raises(ValueError, match="Sleep Cycle"):
        save_report(first.db, first.user_id, "wrong.pdf", "ResMed CPAP",
                    date(2026, 9, 13), date(2026, 10, 12),
                    {"sleep_quality_pct": 68})
