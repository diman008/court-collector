"""File ingestion tests use synthetic DOCX and PDF data, never real cases."""
from io import BytesIO
from zipfile import ZipFile
import hashlib
import pytest
from pypdf import PdfWriter
from judicial_intelligence.ingestion import extract_file, ImportErrorValue, TextUnavailable


def sample_docx(text="Суд упомянул ст. 54.1 НК РФ.") -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:body></w:document>'
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


def sample_empty_pdf() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=400)
    writer.write(output)
    return output.getvalue()


def test_docx_segment_is_not_fake_page():
    data = sample_docx()
    result = extract_file("judgment.docx", data)
    assert result.original_sha256 == hashlib.sha256(data).hexdigest()
    assert result.pagination_verified is False
    assert len(result.segments) == 1
    assert result.segments[0].location_kind == "logical_document"
    assert "54.1" in result.segments[0].text


def test_blank_pdf_needs_explicit_ocr():
    with pytest.raises(TextUnavailable, match="OCR"):
        extract_file("scanned.pdf", sample_empty_pdf())


@pytest.mark.parametrize("name,data",[
    ("fake.pdf", b"malformed"), ("fake.docx", b"not-zip"),
    ("fake.txt", b"text"), ("blank.pdf", b""),
])
def test_reject_unsupported(name, data):
    with pytest.raises(ImportErrorValue):
        extract_file(name, data)


def test_size_limit():
    with pytest.raises(ImportErrorValue, match="8 MiB"):
        extract_file("big.docx", b"x" * (8*1024*1024 + 1))
