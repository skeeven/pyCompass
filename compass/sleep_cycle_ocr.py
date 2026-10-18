"""Bounded, ephemeral OCR fallback for scanned Sleep Cycle PDF exports."""

import io

import fitz
import pytesseract
from PIL import Image


def recognize_sleep_cycle_pdf(data):
    """Read scanned PDF pages without persisting images or extracted text."""
    if not data or len(data) > 8 * 1024 * 1024:
        raise ValueError("PDF must be non-empty and at most 8 MB.")
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                raise ValueError("Encrypted PDFs are not supported.")
            if not 1 <= len(doc) <= 30:
                raise ValueError("Sleep Cycle PDF must contain 1–30 pages.")
            pages = []
            for page in doc:
                # 2x rasterization: avoid unbounded pixel buffers.
                if (page.rect.width <= 0 or page.rect.height <= 0
                        or page.rect.width * page.rect.height * 4 > 16_000_000):
                    raise ValueError("PDF page is too large to process safely.")
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                pages.append(pytesseract.image_to_string(image, config="--psm 3"))
        result = "\n".join(pages).strip()
        if not result:
            raise ValueError("No readable text was detected. Try a clearer export.")
        return result[:40000]
    except ValueError:
        raise
    except pytesseract.TesseractNotFoundError as exc:
        raise ValueError(
            "OCR is not installed. On Mac, run: brew install tesseract"
        ) from exc
    except Exception as exc:
        raise ValueError("Unable to visually read this Sleep Cycle PDF.") from exc
