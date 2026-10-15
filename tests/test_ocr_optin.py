"""Opt-in OCR behavior is tested with an injected local recognizer, no binary needed."""
from io import BytesIO
import pytest
from pypdf import PdfWriter
from judicial_intelligence.ingestion import extract_file, TextUnavailable
from judicial_intelligence.ocr import recognize_pages, OCRUnavailable


def blank_pdf():
    out = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=350, height=350)
    writer.write(out)
    return out.getvalue()


def test_default_has_no_ocr():
    with pytest.raises(TextUnavailable, match="OCR"):
        extract_file("scan.pdf", blank_pdf())


def test_opt_in_preserves_physical_page():
    calls = []
    def local_engine(raw, indices):
        calls.append(indices)
        return {indices[0]: "Суд сослался на ст. 54.1 НК РФ"}
    parsed = extract_file("scan.pdf", blank_pdf(), use_ocr=True, ocr_engine=local_engine)
    assert calls == [[1]]
    assert parsed.segments[0].index == 1
    assert parsed.segments[0].location_kind == "ocr_page"
    assert parsed.pagination_verified is True
    assert any("OCR text is unverified" in warning for warning in parsed.warnings)


def test_ocr_explicit_page_limit():
    with pytest.raises(OCRUnavailable):
        recognize_pages(b"%PDF-1.4", list(range(1, 14)))


def test_empty_ocr_is_not_success():
    with pytest.raises(TextUnavailable):
        extract_file("scan.pdf", blank_pdf(), use_ocr=True,
                     ocr_engine=lambda _raw, _pages: {1: ""})
