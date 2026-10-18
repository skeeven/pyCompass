"""OCR and structured parsing for ResMed myAir sleep therapy reports.

The original PDF and OCR text are not persisted. Only confirmed metrics are saved.
"""

import io
import re
from datetime import datetime

import fitz
import pytesseract
from PIL import Image

HEADER = re.compile(
    r"(?im)^\s*(?P<start>[A-Za-z]{3}\s+\d{1,2},?\s+\d{4})"
    r"\s*[-–—]\s*"
    r"(?P<end>[A-Za-z]{3}\s+\d{1,2},?\s+\d{4})"
    r"\s*\(within\s+\d+\s+days\)"
)


def _date(value):
    return datetime.strptime(value.replace(",", ""), "%b %d %Y").date()


def recognize_resmed_pdf(data):
    """OCR the PDF as displayed, bypassing broken embedded font character maps."""
    if not data or len(data) > 8 * 1024 * 1024:
        raise ValueError("PDF must be non-empty and at most 8 MB.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        if doc.needs_pass or len(doc) > 3:
            raise ValueError("Use an unlocked ResMed PDF with at most 3 pages.")
        parts = []
        for page in doc:
            # Avoid extremely large/hostile page sizes exhausting server memory.
            if page.rect.width <= 0 or page.rect.height <= 0:
                raise ValueError("PDF page dimensions are invalid.")
            if page.rect.width * page.rect.height * 9 > 20_000_000:
                raise ValueError("PDF page is too large to process safely.")
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            parts.append(pytesseract.image_to_string(img, config="--psm 3"))
        doc.close()
        return "\n".join(parts)
    except ValueError:
        raise
    except pytesseract.TesseractNotFoundError as exc:
        raise ValueError(
            "OCR is not installed. On Mac, run: brew install tesseract"
        ) from exc
    except Exception as exc:
        raise ValueError("Could not visually read this PDF.") from exc


def parse_resmed_periods(text):
    """Parse only values associated with one explicitly dated report section."""
    periods = []
    matches = list(HEADER.finditer(text))
    for idx, header in enumerate(matches):
        segment = text[header.end():matches[idx + 1].start() if idx + 1 < len(matches) else len(text)]
        # Only the summary table, not the charts or later labels.
        segment = re.split(r"(?im)^\s*Usage hours\s*$", segment, maxsplit=1)[0]
        usage = re.search(r"Average usage\s*(\d+)\s*hours?\s*(\d+)\s*minutes?", segment, re.I)
        leak = re.search(r"Leak\s*95th\s*%\s*(\d+(?:\.\d+)?)\s*L\s*/\s*min", segment, re.I)
        ahi = re.search(r"Average AHI\s*(\d+(?:\.\d+)?)\s*events?\s*per\s*hour", segment, re.I)
        counts = {}
        for hours in (4, 6):
            match = re.search(
                rf"Days used\s*[^\n\r]{{0,7}}?{hours}\s*hours\s*(\d+)\s*/\s*(\d+)",
                segment, re.I,
            )
            if match:
                counts[hours] = (int(match.group(1)), int(match.group(2)))
        try:
            start, end = _date(header.group("start")), _date(header.group("end"))
        except ValueError:
            continue
        if start > end:
            continue
        metrics = {}
        if usage:
            metrics["cpap_usage_hours"] = round(int(usage.group(1)) + int(usage.group(2)) / 60, 4)
        if ahi:
            metrics["ahi"] = float(ahi.group(1))
        if leak:
            metrics["leak_l_min"] = float(leak.group(1))
        if 4 in counts:
            metrics["nights_over_four_hours"] = counts[4][0]
        if 6 in counts:
            metrics["nights_over_six_hours"] = counts[6][0]
        periods.append({
            "start": start,
            "end": end,
            "metrics": metrics,
            "denominators": {
                "nights_over_four_hours": counts[4][1] if 4 in counts else None,
                "nights_over_six_hours": counts[6][1] if 6 in counts else None,
            },
        })
    return periods
