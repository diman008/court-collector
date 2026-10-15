"""Evidence chain, case history and versioned law without fabricated status."""
from io import BytesIO
from zipfile import ZipFile
import hashlib
import pytest
from judicial_intelligence.evidence import EvidenceStore


def docx(text: str) -> bytes:
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:body></w:document>'
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


@pytest.fixture
def db(tmp_path):
    return EvidenceStore(str(tmp_path / "evidence.db"))


def test_original_bytes_hash_and_citation_offsets(db):
    db.put_case("А40-123/2025")
    source = docx("Сторона цитировала ст. 54.1 НК РФ, применимость неизвестна.")
    result = db.ingest("А40-123/2025", "court.docx", source, "user_provided")
    duplicate = db.ingest("А40-123/2025", "same.docx", source, "user_provided")
    assert result["file_sha256"] == hashlib.sha256(source).hexdigest()
    assert not result["duplicate"] and duplicate["duplicate"]
    assert result["id"] == duplicate["id"]
    assert not result["pagination_verified"]
    assert result["verification_status"] == "unverified_user_input"
    report = db.evidence_report("А40-123/2025")
    assert len(report["mentions"]) == 1
    mention = report["mentions"][0]
    assert mention["file_id"] == result["id"]
    assert mention["quote"] == "ст. 54.1 НК РФ"
    assert mention["location_kind"] == "logical_document"
    assert report["legal_conclusions"] == []
    with db.connect() as conn:
        original = conn.execute("SELECT original_bytes FROM evidence_files WHERE id=?", (result["id"],)).fetchone()[0]
    assert original == source


def test_timeline_relationships_cross_case_protected(db):
    db.put_case("А40-123/2025")
    db.put_case("А55-456/2025")
    first = db.add_act("А40-123/2025", court="Первый суд", act_date="2025-03-20",
                       instance="first", act_type="решение")
    appeal = db.add_act("А40-123/2025", court="Апелляционный суд", act_date="2025-05-21",
                        instance="appeal", act_type="постановление", prior_act_id=first["id"],
                        relation_kind="reverses")
    assert appeal["prior_act_id"] == first["id"]
    assert db.timeline("А40-123/2025")["finality_verified"] is False
    assert [row["instance"] for row in db.timeline("А40-123/2025")["acts"]] == ["first", "appeal"]
    with pytest.raises(ValueError, match="another case"):
        db.add_act("А55-456/2025", court="Суд", act_date="2025-06-20",
                   instance="appeal", act_type="решение", prior_act_id=first["id"], relation_kind="reverses")


def test_norm_versions_are_date_anchored_and_not_verified(db):
    db.register_norm("НК РФ:54.1", "Редакция А", "2017-08-19", "https://example.org/a", "2023-12-31")
    db.register_norm("НК РФ:54.1", "Редакция Б", "2024-01-01", "https://example.org/b")
    version = db.norm_at("НК РФ:54.1", "2022-04-01")
    assert len(version) == 1 and version[0]["text_content"] == "Редакция А"
    assert version[0]["verification_status"] == "unverified_user_input"
    assert db.norm_at("НК РФ:54.1", "2010-01-01") == []
    with pytest.raises(ValueError, match="ends before"):
        db.register_norm("НК РФ:77", "Ошибка", "2026-01-01", "https://example.org/c", "2025-01-01")
