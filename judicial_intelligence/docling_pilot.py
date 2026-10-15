"""Opt-in OFFLINE Docling pilot; not a court-source verification tool.

This uses only DocumentStream created from caller-provided in-memory bytes.
No URLs, no implicit uploads, no Docling models installed by base package.
Test this in a restricted process with pre-cached model artifacts.
"""
from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from pathlib import Path
import hashlib
import os

from .ingestion import ExtractedFile, ImportErrorValue, MAX_FILE_BYTES, MAX_PAGES, MAX_TOTAL_CHARS, Segment


class DoclingUnavailable(ImportErrorValue):
    pass


def pilot_docling(filename: str, raw: bytes, *, converter=None) -> ExtractedFile:
    if os.getenv("HF_HUB_OFFLINE") != "1":
        raise DoclingUnavailable("Set HF_HUB_OFFLINE=1 and pre-cache Docling models before local conversion")
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_FILE_BYTES:
        raise ImportErrorValue("Input must be 1 byte to 8 MiB")
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".docx"):
        raise ImportErrorValue("Only local PDF and DOCX inputs are supported")
    if converter is None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise DoclingUnavailable("Install the optional [docling] dependencies locally") from exc
        converter = DocumentConverter()
    try:
        from docling.datamodel.base_models import DocumentStream
    except ImportError:
        # Test-double converter supports a minimal stream-like object with name/stream.
        if converter.__class__.__module__.startswith("docling"):
            raise DoclingUnavailable("Docling DocumentStream not available")
        from types import SimpleNamespace
        source = SimpleNamespace(name=Path(filename).name, stream=BytesIO(raw))
    else:
        source = DocumentStream(name=Path(filename).name, stream=BytesIO(raw))
    try:
        result = converter.convert(source, max_num_pages=MAX_PAGES, max_file_size=MAX_FILE_BYTES)
        doc = result.document
        groups = defaultdict(list)
        missing = []
        for block in getattr(doc, "texts", []):
            content = getattr(block, "text", "")
            if not isinstance(content, str) or not content.strip():
                continue
            pages = {
                getattr(p, "page_no", None)
                for p in getattr(block, "prov", [])
                if isinstance(getattr(p, "page_no", None), int)
            }
            if ext == ".pdf" and len(pages) == 1:
                page_no = next(iter(pages))
                if not (1 <= page_no <= MAX_PAGES):
                    raise ImportErrorValue("Docling returned invalid PDF page number")
                groups[page_no].append(content)
            else:
                missing.append(content)
        segments = [
            Segment(index, "physical_page", "\n".join(items))
            for index, items in sorted(groups.items())
        ]
        if missing:
            segments.append(Segment(0, "logical_document", "\n".join(missing)))
        if not segments:
            fallback = doc.export_to_markdown()
            if fallback.strip():
                segments = [Segment(0, "logical_document", fallback)]
        if not segments:
            raise ImportErrorValue("Docling returned no text")
        if sum(len(s.text) for s in segments) > MAX_TOTAL_CHARS:
            raise ImportErrorValue("Docling output exceeds character limit")
    except ImportErrorValue:
        raise
    except Exception as exc:
        raise ImportErrorValue("Offline Docling conversion failed") from exc
    verified_pages = ext == ".pdf" and bool(groups) and not missing
    return ExtractedFile(
        format=ext.lstrip("."),
        original_sha256=hashlib.sha256(raw).hexdigest(),
        size=len(raw),
        segments=tuple(segments),
        pagination_verified=verified_pages,
        warnings=(
            "Pilot Docling extraction only; text and source remain unverified.",
            "Physical page indices are available only where Docling supplied page provenance.",
            "Docling output is not automatically ingested into the evidence store.",
        ),
    )
