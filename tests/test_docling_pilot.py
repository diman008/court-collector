"""Docling pilot tested without downloading ML models or uploading real records."""
from types import SimpleNamespace
import hashlib

import pytest
from judicial_intelligence.docling_pilot import pilot_docling, DoclingUnavailable
from judicial_intelligence.ingestion import ImportErrorValue


class FakeConverter:
    def __init__(self, include_pages=True):
        self.include_pages=include_pages
        self.calls=[]
    def convert(self, stream, **kwargs):
        self.calls.append((stream.name,kwargs,stream.stream.getvalue()))
        text1=SimpleNamespace(text="Статья 54.1 НК РФ", prov=[
            SimpleNamespace(page_no=3)] if self.include_pages else [])
        text2=SimpleNamespace(text="Проверка эксперта обязательна", prov=[
            SimpleNamespace(page_no=4)] if self.include_pages else [])
        doc=SimpleNamespace(texts=[text1,text2],export_to_markdown=lambda:"Markdown test")
        return SimpleNamespace(document=doc)


def test_docling_explicit_offline_requirements(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE",raising=False)
    with pytest.raises(DoclingUnavailable,match="HF_HUB_OFFLINE"):
        pilot_docling("sample.pdf",b"%PDF-1.4",converter=FakeConverter())


def test_docling_pilot_retains_page_and_sha_without_network(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE","1")
    fake=FakeConverter()
    raw=b"%PDF-1.4 anonymous test input"
    result=pilot_docling("sample.pdf",raw,converter=fake)
    assert fake.calls[0][0]=="sample.pdf"
    assert fake.calls[0][1]["max_num_pages"] == 200
    assert fake.calls[0][2]==raw
    assert result.original_sha256==hashlib.sha256(raw).hexdigest()
    assert result.pagination_verified is True
    assert [(s.index,s.location_kind) for s in result.segments]==[
        (3,"physical_page"),(4,"physical_page")]
    assert "not automatically ingested" in result.warnings[-1]


def test_missing_docling_provenance_never_invents_page(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE","1")
    result=pilot_docling("sample.docx",b"PK anything",converter=FakeConverter(False))
    assert result.pagination_verified is False
    assert len(result.segments)==1
    assert result.segments[0].location_kind=="logical_document"
    assert result.segments[0].index==0


@pytest.mark.parametrize("name,raw",[
    ("sample.txt",b"content"),("sample.pdf",b""),
    ("sample.pdf",b"x"* (8*1024*1024+1)),
])
def test_docling_rejects_unsupported_or_oversized(monkeypatch,name,raw):
    monkeypatch.setenv("HF_HUB_OFFLINE","1")
    with pytest.raises(ImportErrorValue):
        pilot_docling(name,raw,converter=FakeConverter())
