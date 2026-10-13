"""Privacy-first, text-based sleep report PDF intake."""

import io
import re
from datetime import date, datetime, timezone
from uuid import uuid4

from pypdf import PdfReader

METRICS = {
    "cpap_usage_hours": ("CPAP usage", "hours/night"),
    "ahi": ("Apnea-hypopnea index", "events/hour"),
    "leak_l_min": ("Mask leak", "L/min"),
    "sleep_hours": ("Sleep duration", "hours/night"),
    "nights_over_four_hours": ("Nights with 4+ hours CPAP", "nights"),
}


def extract_pdf_text(data):
    """Extract text only; never persist original PDF bytes."""
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("PDF exceeds the 8 MB limit.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")
        if len(reader.pages) > 30:
            raise ValueError("PDF exceeds the 30-page limit.")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to read this PDF.") from exc
    if not text.strip():
        raise ValueError("No selectable text found. Scanned PDFs are not supported yet.")
    if not re.search(
        r"\\b(?:ResMed|myAir|Average usage|Average AHI|Sleep therapy|Sleep Cycle)\\b",
        text, re.IGNORECASE,
    ):
        raise ValueError(
            "PDF text is unreadable or unsupported. This report needs OCR; "
            "no measurements were saved."
        )
    return text[:40000]


def suggested_metrics(text):
    """Conservative suggestions; all values must be confirmed by the user."""
    patterns = {
        "ahi": r"\b(?:AHI|apnea.hypopnea index)\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
        "leak_l_min": r"\b(?:95th percentile leak|mask leak)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:L/min|lpm)\b",
    }
    values = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            values[key] = float(match.group(1))
    return values


def save_report(db, user_id, filename, kind, start, end, metrics):
    """Save only user-confirmed aggregate metrics and provenance."""
    if kind not in {"ResMed CPAP", "Sleep Cycle"}:
        raise ValueError("Unsupported report type.")
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise ValueError("Choose a valid report date range.")
    if not metrics or set(metrics) - set(METRICS):
        raise ValueError("Select at least one supported metric.")
    for key, value in metrics.items():
        if not isinstance(value, (float, int)) or not 0 <= value <= 10000:
            raise ValueError("Invalid metric value.")
    with db.connect() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
            raise ValueError("Account is unavailable.")
        report_id = str(uuid4())
        conn.execute(
            """INSERT INTO health_reports
            (id, user_id, uploaded_at, filename, report_type, status,
             period_start, period_end) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (report_id, user_id, datetime.now(timezone.utc).isoformat(),
             filename[:200], kind, "verified", start.isoformat(), end.isoformat()),
        )
        for key, value in metrics.items():
            conn.execute(
                """INSERT INTO health_report_metrics
                (id, report_id, user_id, metric_name, metric_value, unit, source_label)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid4()), report_id, user_id, key, float(value),
                 METRICS[key][1], "User verified period aggregate"),
            )
    return report_id
