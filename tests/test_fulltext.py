"""FTS5 search: Russian matching, provenance, safe terms, migrations and case filters."""
from io import BytesIO
from zipfile import ZipFile
import pytest
from fastapi.testclient import TestClient

from judicial_intelligence.api import create_app
from judicial_intelligence.search import SearchStore, safe_fts_query
from judicial_intelligence.evidence import EvidenceStore


def make_docx(text):
    b = BytesIO()
    xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:p><w:r><w:t>' + text +
           '</w:t></w:r></w:p></w:body></w:document>')
    with ZipFile(b,"w") as z:
        z.writestr("word/document.xml", xml)
    return b.getvalue()


def test_existing_evidence_migration_and_idempotent_index(tmp_path):
    path = str(tmp_path / "index.db")
    older = EvidenceStore(path)
    older.put_case("А40-123/2025",court="Арбитражный суд Москвы")
    file = older.ingest("А40-123/2025", "court.docx",
                        make_docx("Доказательства поставки товара и ст. 54.1 НК РФ."),
                        "user_provided")
    older.put_document("А40-123/2025", "Поставка подтверждена актом сверки", "user_provided")
    new = SearchStore(path)
    hit = new.search_text("поставки")
    assert len(hit["results"]) == 1
    first = hit["results"][0]
    assert first["source_id"] == file["id"]
    assert first["sha256"] == file["file_sha256"]
    assert first["location_kind"] == "logical_document"
    assert first["verification_status"] == "unverified_user_input"
    assert "[поставки]" in first["excerpt"].lower()
    assert new.search_text("поставка")["results"][0]["source_type"] == "text_document"
    assert len(SearchStore(path).search_text("поставки")["results"]) == 1


def test_new_uploads_and_filters_indexed_without_rebuild(tmp_path):
    store = SearchStore(str(tmp_path / "new.db"))
    for number,court in (("А40-123/2025","Москва"),("А55-456/2025","Самара")):
        store.put_case(number,court=court)
        store.put_document(number,"Налоговый контроль и доказательства", "user_provided")
    results = store.search_text("налоговый контроль",court="Москва")
    assert [v["case_number"] for v in results["results"]] == ["А40-123/2025"]
    results2 = store.search_text("доказательства",case_number="А55-456/2025")
    assert len(results2["results"]) == 1
    assert results2["coverage"] == "local_imports_only"


@pytest.mark.parametrize("query", [
    "", " ", "a" * 161, "one two three four five six seven eight nine ten eleven twelve thirteen",
    '" OR 1=1 --',
])
def test_bad_or_hostile_fts_queries_never_run_operators(query):
    if query == '" OR 1=1 --':
        assert safe_fts_query(query) == '"OR" AND "1" AND "1"'
    else:
        with pytest.raises(ValueError):
            safe_fts_query(query)


def test_fulltext_rest_authenticated(tmp_path):
    path=str(tmp_path / "api.db")
    store=SearchStore(path)
    store.put_case("А40-123/2025")
    store.put_document("А40-123/2025","Налоговая реконструкция невозможна", "user_provided")
    client=TestClient(create_app(path,api_key="secret"))
    assert client.get("/v1/fulltext",params={"q":"реконструкция"}).status_code == 401
    h={"X-API-Key":"secret"}
    ok=client.get("/v1/fulltext",params={"q":"реконструкция"},headers=h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["results"][0]["case_number"]=="А40-123/2025"
    assert client.get("/v1/fulltext",params={"q":"!@#$%"},headers=h).status_code == 422
