"""Permitted source boundary: explicit local imports only in MVP."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from .core import MAX_CHARS, validate_text

@dataclass(frozen=True)
class ImportedDocument:
    text: str
    source_kind: str
    source_url: str | None = None

class JudicialSource(Protocol):
    def load(self, identifier: str) -> ImportedDocument: ...

class LocalTextExport:
    def load(self, identifier: str) -> ImportedDocument:
        path = Path(identifier)
        if path.suffix.lower() != ".txt" or not path.is_file():
            raise ValueError("An existing .txt export is required")
        if path.stat().st_size > MAX_CHARS * 4:
            raise ValueError("File too large")
        text = path.read_text(encoding="utf-8")
        validate_text(text)
        return ImportedDocument(text=text, source_kind="official_export")

class LiveKadAdapter:
    def load(self, identifier: str) -> ImportedDocument:
        raise NotImplementedError("Live KAD requires permitted access and verified integration")
