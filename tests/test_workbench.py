"""Analyst API/HTML tests with entirely synthetic local judicial evidence."""
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from judicial_intelligence.api import create_app
from judicial_intelligence.evidence import EvidenceStore


def fake_docx(message="Стороны сослались на ст. 54.1 НК РФ."):
    xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:p><w:r><w:t>' + message +
           '</w:t></w:r></w:p></w:body></w:document>')
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


def test_dashboard_security_headers_and_bundled_static(tmp_path):
    client = TestClient(create_app(str(tmp_path / "dashboard.db"), api_key="secret"))
    page = client.get("/analyst")
    assert page.status_code == 200
    assert "Судебная аналитика" in page.text
    assert "default-src 'none'" in page.headers["content-security-policy"]
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["cache-control"] == "no-store"
    assert "X-API-Key" not in page.text
    javascript = client.get("/analyst.js")
    assert javascript.status_code == 200
    assert "textContent" in javascript.text
    assert "innerHTML" not in javascript.text
    assert "localStorage" not in javascript.text
    assert "sessionStorage" not in javascript.text
    assert client.get("/analyst.css").status_code == 200


def test_local_dossier_has_exact_provenance_and_no_invented_conclusions(tmp_path):
    path = str(tmp_path / "dossier.db")
    db = EvidenceStore(path)
    db.put_case("А40-123/2025", title="Тест судебной практики", court="Тестовый суд")
    evidence = db.ingest("А40-123/2025", "акт.docx", fake_docx(),
                         "user_provided", source_url="https://example.org/test")
    db.add_act("А40-123/2025", court="Тестовый суд", act_date="2025-08-20",
               instance="first", act_type="решение", linked_file_id=evidence["id"])
    client = TestClient(create_app(path, api_key="secret"))
    params = {"case_number": "А40-123/2025"}
    assert client.get("/v1/dossier", params=params).status_code == 401
    response = client.get("/v1/dossier", params=params, headers={"X-API-Key": "secret"})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["counts"]["evidence_files"] == 1
    assert report["counts"]["acts"] == 1
    assert report["counts"]["norm_articles"] == 1
    assert report["norm_articles"] == ["54.1"]
    assert report["legal_conclusions"] == []
    assert report["judicial_finality_verified"] is False
    assert report["source_verification"] == "unverified"
    mention = report["literal_references"][0]
    assert mention["file_id"] == evidence["id"]
    assert mention["sha256"] == evidence["file_sha256"]
    assert mention["quote"] == "ст. 54.1 НК РФ"
    assert mention["location_kind"] == "logical_document"
    assert report["unresolved_checks"]


def test_empty_dossier_and_no_cross_case_leak(tmp_path):
    path = str(tmp_path / "empty.db")
    db = EvidenceStore(path)
    db.put_case("А55-456/2025")
    client = TestClient(create_app(path, api_key="secret"))
    h = {"X-API-Key": "secret"}
    valid = client.get("/v1/dossier", headers=h, params={"case_number": "А55-456/2025"})
    assert valid.status_code == 200
    assert valid.json()["counts"]["literal_mentions"] == 0
    assert valid.json()["legal_conclusions"] == []
    missing = client.get("/v1/dossier", headers=h, params={"case_number": "А40-999/2025"})
    assert missing.status_code == 404


def test_detect_tampered_original_in_dossier(tmp_path):
    path = str(tmp_path / "tampered.db")
    db = EvidenceStore(path)
    db.put_case("А40-123/2025")
    file = db.ingest("А40-123/2025", "акт.docx", fake_docx(), "user_provided")
    with db.connect() as conn:
        conn.execute("UPDATE evidence_files SET original_bytes=? WHERE id=?", (b"changed", file["id"]))
    client = TestClient(create_app(path, api_key="secret"))
    response = client.get("/v1/dossier", headers={"X-API-Key": "secret"},
                          params={"case_number": "А40-123/2025"})
    assert response.status_code == 200
    assert response.json()["integrity_failures"] == [file["id"]]
