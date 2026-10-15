"""Explicit opt-in, offline OCR of textless PDF pages.

Tesseract is a local binary; no cloud OCR, proxy or remote file upload.
This is NOT a full sandbox. Only use trusted/authorized input in an isolated process.
"""
from __future__ import annotations

MAX_OCR_PAGES = 12
MAX_PIXELS_PER_PAGE = 5_000_000


class OCRUnavailable(ValueError):
    pass


def recognize_pages(pdf_bytes: bytes, page_numbers: list[int]) -> dict[int, str]:
    """Return OCR text keyed by 1-based PDF physical page; fail closed."""
    indices = list(dict.fromkeys(page_numbers))
    if not indices or len(indices) > MAX_OCR_PAGES or any(n < 1 for n in indices):
        raise OCRUnavailable("OCR is limited to 1-12 selected pages")
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError as exc:
        raise OCRUnavailable("Install the optional ocr extra and local Tesseract with rus+eng data") from exc
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        if any(n > len(pdf) for n in indices):
            raise OCRUnavailable("Page is outside PDF")
        result = {}
        for n in indices:
            page = pdf[n - 1]
            # 2x = 144 dpi; fixed resolution bounds rasterization resources.
            if page.get_width() * page.get_height() * 4 > MAX_PIXELS_PER_PAGE:
                raise OCRUnavailable("Page raster dimensions exceed OCR limits")
            bitmap = page.render(scale=2)
            image = bitmap.to_pil()
            try:
                value = pytesseract.image_to_string(
                    image, lang="rus+eng", config="--psm 6", timeout=20
                )
            except (RuntimeError, pytesseract.TesseractError) as exc:
                raise OCRUnavailable("Tesseract failed; verify rus+eng data and file quality") from exc
            result[n] = value
        return result
    except OCRUnavailable:
        raise
    except Exception as exc:
        raise OCRUnavailable("Offline OCR could not process PDF") from exc
