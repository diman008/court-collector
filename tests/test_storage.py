import pytest
from judicial_intelligence.storage import Database, MissingCase

@pytest.fixture
def store(tmp_path):
    return Database(str(tmp_path / "cases.sqlite3"))

def test_roundtrip_deduplicate_and_provenance(store):
    store.put_case("A40-123/2025", title="Тест", court="Арбитражный суд")
    first = store.put_document("А40-123/2025", "Ссылка: ст. 171 НК РФ.", "user_provided", "https://example.org/source")
    second = store.put_document("А40-123/2025", "Ссылка: ст. 171 НК РФ.", "user_provided")
    assert not first["duplicate"] and second["duplicate"]
    assert first["id"] == second["id"]
    assert len(store.documents("А40-123/2025")) == 1
    report = store.report("А40-123/2025")
    assert report["documents_count"] == 1
    assert report["article_mentions"][0]["document_id"] == first["id"]
    assert report["article_mentions"][0]["sha256"] == first["sha256"]
    assert report["legal_conclusions"] == []

def test_literal_search_and_case_presence(store):
    store.put_case("А40-900/2024", title="100% дело")
    assert len(store.list_cases("100%")) == 1
    assert store.list_cases("100_") == []
    with pytest.raises(MissingCase):
        store.put_document("А40-999/2024", "ст. 77 НК РФ", "user_provided")
