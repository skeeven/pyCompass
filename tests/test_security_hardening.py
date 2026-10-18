"""Security regression checks for upload minimization and credential handling."""

from dataclasses import replace
from datetime import date

import fitz
import pytest

from compass.config import Settings
from compass.health_reports import save_report
from compass.resmed_ocr import recognize_resmed_pdf


def test_sensitive_configuration_not_in_repr():
    settings = Settings(
        database_url="sqlitecloud://example/compass?apikey=secret-db",
        openai_api_key="sk-private-key",
        zoho_client_secret="secret-zoho",
        zoho_refresh_token="secret-refresh",
    )
    displayed = repr(settings)
    for secret in ("secret-db", "sk-private-key", "secret-zoho", "secret-refresh"):
        assert secret not in displayed


def test_original_pdf_name_is_not_saved(users):
    owner, _ = users
    save_report(
        owner.db, owner.user_id,
        "private-path/report-full-legal-name-birthdate.pdf",
        "ResMed CPAP", date(2026, 9, 13), date(2026, 10, 12),
        {"ahi": 0.9},
    )
    record = owner.rows("health_reports")[0]
    assert record["filename"] == "ResMed report.pdf"
    assert "legal-name" not in str(record)


def test_ocr_rejects_oversized_page_without_rendering():
    doc = fitz.open()
    doc.new_page(width=2500, height=2500)
    data = doc.tobytes()
    doc.close()
    with pytest.raises(ValueError, match="too large"):
        recognize_resmed_pdf(data)


def test_ocr_rejects_empty_data():
    with pytest.raises(ValueError, match="non-empty"):
        recognize_resmed_pdf(b"")
