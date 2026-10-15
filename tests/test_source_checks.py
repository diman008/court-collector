"""Human-only source checks are append-only, case-bound, never cryptographic verification."""
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from judicial_intelligence.api import create_app
from judicial_intelligence.source_checks import ReviewStore, validated_url


def sample_docx():
    b = BytesIO()
    xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:p><w:r><w:t>ст. 54.1 НК РФ</w:t></w:r></w:p></w:body></w:document>')
    with ZipFile(b, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return b.getvalue()


@pytest.mark.parametrize("name,url", [
    ("kad_casecard", "https://kad.arbitr.ru.evil.invalid/case"),
    ("electronic_signature", "https://check.arbitr.ru.evil.invalid/"),
    ("kad_casecard", "http://kad.arbitr.ru/"),
    ("kad_casecard", "https://user:pass@kad.arbitr.ru/"),
    ("legal_text", "https://pravo.gov.ru:4043/"),
    ("unknown", "https://kad.arbitr.ru/"),
])
def test_source_host_spoof_rejected(name, url):
    with pytest.raises(ValueError):
        validated_url(name, url)


def test_append_only_manual_review_and_cross_case_check(tmp_path):
    store = ReviewStore(str(tmp_path / "manual.db"))
    store.put_case("А40-123/2025")
    store.put_case("А55-456/2025")
    evidence = store.ingest("А40-123/2025", "decision.docx", sample_docx(), "user_provided")
    review = store.record_source_check(
        "А40-123/2025",
        source_type="electronic_signature",
        source_url="https://check.arbitr.ru/",
        claimed_result="match_claimed",
        reviewer_alias="local-user",
        reviewer_note="Вручную посмотрел карточку проверки",
        file_id=evidence["id"],
    )
    assert review["independent_verification"] == "not_performed"
    assert review["file_sha256_at_review"] == evidence["file_sha256"]
    assert len(store.list_source_checks("А40-123/2025")) == 1
    assert store.verification_packet("А40-123/2025",evidence["id"])["signature_verification_status"] == "not_performed"
    with pytest.raises(ValueError,match="within the case"):
        store.record_source_check(
            "А55-456/2025",
            source_type="electronic_signature",
            source_url="https://check.arbitr.ru/",
            claimed_result="match_claimed",
            reviewer_alias="local-user",
            file_id=evidence["id"],
        )


def test_review_rest_auth_and_dossier_never_asserts_signature(tmp_path):
    client=TestClient(create_app(str(tmp_path / "review.db"),api_key="secret"))
    h={"X-API-Key":"secret"}
    assert client.post("/v1/cases",headers=h,json={"case_number":"А40-123/2025"}).status_code == 201
    payload={
        "case_number":"А40-123/2025",
        "source_type":"kad_casecard",
        "source_url":"https://kad.arbitr.ru/",
        "claimed_result":"inconclusive",
        "reviewer_alias":"test-analyst",
    }
    assert client.post("/v1/reviews",json=payload).status_code == 401
    saved=client.post("/v1/reviews",headers=h,json=payload)
    assert saved.status_code == 201, saved.text
    assert saved.json()["independent_verification"] == "not_performed"
    records=client.get("/v1/reviews",headers=h,params={"case_number":"А40-123/2025"})
    assert records.status_code == 200
    assert records.json()["verification_scope"] == "user_assertions_only"
    assert len(records.json()["records"]) == 1
    report=client.get("/v1/dossier",headers=h,params={"case_number":"А40-123/2025"}).json()
    assert report["counts"]["manual_checks"] == 1
    assert report["source_verification"] == "unverified"
    assert report["judicial_finality_verified"] is False
    assert report["legal_conclusions"] == []


def test_refuses_fake_success_from_wrong_site(tmp_path):
    client=TestClient(create_app(str(tmp_path / "invalid.db"),api_key="secret"))
    h={"X-API-Key":"secret"}
    client.post("/v1/cases",headers=h,json={"case_number":"А40-123/2025"})
    result=client.post("/v1/reviews",headers=h,json={
        "case_number":"А40-123/2025",
        "source_type":"electronic_signature",
        "source_url":"https://kad.arbitr.ru/",
        "claimed_result":"match_claimed",
        "reviewer_alias":"analyst",
    })
    assert result.status_code == 422
