"""Integrity verification is NOT a signature check."""
from io import BytesIO
from zipfile import ZipFile
from fastapi.testclient import TestClient
from judicial_intelligence.api import create_app
from judicial_intelligence.evidence import EvidenceStore


def sample_docx():
    text = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Норма 54.1</w:t></w:r></w:p></w:body></w:document>'
    b = BytesIO()
    with ZipFile(b, "w") as archive:
        archive.writestr("word/document.xml", text)
    return b.getvalue()


def test_packet_and_detect_modified_original(tmp_path):
    db = EvidenceStore(str(tmp_path / "verification.db"))
    db.put_case("А40-123/2025")
    row = db.ingest("А40-123/2025", "decision.docx", sample_docx(), "user_provided")
    packet = db.verification_packet("А40-123/2025", row["id"])
    assert packet["stored_bytes_match_sha256"] is True
    assert packet["signature_verification_status"] == "not_performed"
    assert not packet["judicial_finality_verified"]
    assert packet["official_signature_check_url"] == "https://check.arbitr.ru/"
    with db.connect() as conn:
        conn.execute("UPDATE evidence_files SET original_bytes=? WHERE id=?", (b"tampered", row["id"]))
    assert db.verification_packet("А40-123/2025", row["id"])["stored_bytes_match_sha256"] is False


def test_authenticated_packet_api_and_cross_case_block(tmp_path):
    path = str(tmp_path / "api.db")
    client = TestClient(create_app(path, api_key="secret"))
    h = {"X-API-Key": "secret"}
    for case in ["А40-123/2025", "А55-321/2025"]:
        assert client.post("/v1/cases", headers=h, json={"case_number": case}).status_code == 201
    evidence = EvidenceStore(path).ingest("А40-123/2025", "doc.docx", sample_docx(), "user_provided")
    args = {"case_number": "А40-123/2025", "file_id": evidence["id"]}
    assert client.get("/v1/verification-packet", params=args).status_code == 401
    good = client.get("/v1/verification-packet", params=args, headers=h)
    assert good.status_code == 200
    assert good.json()["signature_verification_status"] == "not_performed"
    args["case_number"] = "А55-321/2025"
    assert client.get("/v1/verification-packet", params=args, headers=h).status_code == 404
