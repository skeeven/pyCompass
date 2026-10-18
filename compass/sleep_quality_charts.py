"""Bounded preview of user-provided Sleep Cycle chart images or image PDFs.

Graph bars and curves do not encode exact numeric readings accessible to OCR.
The user must enter a figure from an explicit source or label it an estimate.
No image or rendered page is stored by this module.
"""

import io

import fitz
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16_000_000


def sleep_quality_chart_preview(data, name):
    """Return a temporary PNG/JPEG image suitable for on-screen confirmation."""
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Chart file must be non-empty and at most 8 MB.")
    suffix = name.rsplit(".", 1)[-1].lower()
    if suffix in {"jpg", "jpeg", "png"}:
        try:
            with Image.open(io.BytesIO(data)) as img:
                if img.format not in {"JPEG", "PNG"}:
                    raise ValueError("Only JPEG and PNG chart images are supported.")
                if img.width * img.height > MAX_PIXELS:
                    raise ValueError("Chart image dimensions are too large.")
                img.verify()
            return data
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("Could not open this chart image.") from exc
    if suffix == "pdf":
        try:
            with fitz.open(stream=data, filetype="pdf") as pdf:
                if pdf.needs_pass or not 1 <= len(pdf) <= 30:
                    raise ValueError("Use an unlocked PDF containing 1–30 pages.")
                page = pdf[0]
                if (page.rect.width <= 0 or page.rect.height <= 0 or
                        page.rect.width * page.rect.height * 4 > MAX_PIXELS):
                    raise ValueError("PDF chart page is too large to preview.")
                return page.get_pixmap(
                    matrix=fitz.Matrix(2, 2), alpha=False
                ).tobytes("png")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Could not render this chart PDF.") from exc
    raise ValueError("Select a PDF, JPG, JPEG or PNG chart.")
