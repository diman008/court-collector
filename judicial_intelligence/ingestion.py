"""Conservative offline extraction of user-supplied PDF and DOCX documents.

Extracted text is not a proof of document authenticity. No OCR/network access.
DOCX pagination is unavailable: its single logical segment is NOT a page.
"""
from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree
import hashlib

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 200
MAX_TOTAL_CHARS = 200_000


class ImportErrorValue(ValueError):
    """Rejected, unreadable or unsupported input."""


class TextUnavailable(ImportErrorValue):
    """PDF is image-based/has no extractable text: manual OCR required."""


@dataclass(frozen=True)
class Segment:
    index: int
    location_kind: str  # physical_page or logical_document
    text: str


@dataclass(frozen=True)
class ExtractedFile:
    format: str
    original_sha256: str
    size: int
    segments: tuple[Segment, ...]
    pagination_verified: bool
    warnings: tuple[str, ...]


def _pdf(raw: bytes) -> tuple[Segment, ...]:
    from pypdf import PdfReader

    if not raw.startswith(b"%PDF-"):
        raise ImportErrorValue("Invalid PDF signature")
    try:
        reader = PdfReader(BytesIO(raw), strict=True)
        if reader.is_encrypted:
            raise ImportErrorValue("Encrypted PDFs need authorized manual decryption")
        if len(reader.pages) > MAX_PAGES:
            raise ImportErrorValue("Too many PDF pages")
        segments = tuple(
            Segment(i, "physical_page", page.extract_text() or "")
            for i, page in enumerate(reader.pages, 1)
        )
    except ImportErrorValue:
        raise
    except Exception as exc:
        raise ImportErrorValue("PDF cannot be parsed safely") from exc
    if not any(s.text.strip() for s in segments):
        raise TextUnavailable("PDF has no extractable text; OCR not executed")
    return segments


def _docx(raw: bytes) -> tuple[Segment, ...]:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with ZipFile(BytesIO(raw)) as archive:
            if len(archive.infolist()) > 2000:
                raise ImportErrorValue("DOCX has too many archive entries")
            item = archive.getinfo("word/document.xml")
            if item.file_size > 4_000_000:
                raise ImportErrorValue("DOCX XML exceeds safe extraction size")
            root = ElementTree.fromstring(archive.read(item))
    except (BadZipFile, KeyError, ElementTree.ParseError, OSError) as exc:
        raise ImportErrorValue("DOCX document.xml is missing or invalid") from exc
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(t.text or "" for t in paragraph.findall(".//w:t", namespace))
        if text.strip():
            paragraphs.append(text)
    return (Segment(1, "logical_document", "\n".join(paragraphs)),)


def extract_file(filename: str, raw: bytes) -> ExtractedFile:
    if not isinstance(raw, bytes) or not raw:
        raise ImportErrorValue("Empty input")
    if len(raw) > MAX_FILE_BYTES:
        raise ImportErrorValue("Input exceeds 8 MiB")
    ext = Path(filename or "").suffix.lower()
    if ext == ".pdf":
        segments = _pdf(raw)
        warnings = ("PDF text extraction does not verify digital signatures.",)
    elif ext == ".docx":
        if not raw.startswith(b"PK"):
            raise ImportErrorValue("Invalid DOCX ZIP signature")
        segments = _docx(raw)
        warnings = ("DOCX has no reliable page mapping; segment 1 is the whole document.",)
    else:
        raise ImportErrorValue("Only PDF and DOCX are supported")
    if not segments or not any(s.text.strip() for s in segments):
        raise TextUnavailable("No extractable text")
    if sum(len(s.text) for s in segments) > MAX_TOTAL_CHARS:
        raise ImportErrorValue("Extracted text exceeds 200000 characters")
    return ExtractedFile(
        format=ext[1:], original_sha256=hashlib.sha256(raw).hexdigest(),
        size=len(raw), segments=segments, pagination_verified=ext == ".pdf",
        warnings=warnings,
    )
