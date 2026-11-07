"""Authorized-source inventory never grants data access or verifies an electronic signature."""
from fastapi.testclient import TestClient

from judicial_intelligence.api import create_app
from judicial_intelligence.source_registry import list_official_sources


def test_all_sources_have_explicit_permission_gates():
    registry = list_official_sources()
    assert registry["automated_case_collection"] == "disabled"
    assert len(registry["sources"]) == 4
    assert all(not source["connector_enabled"] for source in registry["sources"])
    assert all(source["automatic_access_verified"] is False for source in registry["sources"])
    assert all(source["rights_review_status"] == "pending" for source in registry["sources"])
    assert registry["sources"][0]["url"] == "https://kad.arbitr.ru/"


def test_api_source_registry_requires_key(tmp_path):
    client = TestClient(create_app(str(tmp_path / "sources.db"), api_key="secret"))
    assert client.get("/v1/sources").status_code == 401
    response = client.get("/v1/sources", headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    assert response.json()["automated_case_collection"] == "disabled"


def test_reproducible_synthetic_search_precision(tmp_path):
    """Five synthetic case snippets, zero real user/court confidential materials."""
    from judicial_intelligence.search import SearchStore
    store = SearchStore(str(tmp_path / "benchmark.db"))
    samples = {
        "А40-101/2025": "Доказательства поставки товара: товарная накладная, акт приема.",
        "А40-102/2025": "Суд исследовал доказательства поставки и условия сделки.",
        "А55-103/2025": "Аренда нежилого помещения и расторжение договора.",
        "А55-104/2025": "Налоговый контроль. Статья 54.1 НК РФ.",
        "А55-105/2025": "Документы, связанные с поставками мебели.",
    }
    for number, body in samples.items():
        store.put_case(number)
        store.put_document(number, body, "user_provided")
    retrieved = store.search_text("доказательства поставки",limit=20)["results"]
    ids = {item["case_number"] for item in retrieved}
    # Literal-token benchmark. Case 105 is morphological variation, not a false positive.
    relevant = {"А40-101/2025", "А40-102/2025"}
    precision = len(ids & relevant) / len(ids)
    recall = len(ids & relevant) / len(relevant)
    assert ids == relevant
    assert precision == 1.0 and recall == 1.0
    assert store.search_text("аренда")["results"][0]["case_number"] == "А55-103/2025"


def test_ranked_search_benchmark_counts_short_results_and_inflection_misses():
    from scripts.benchmark_ranked_search import evaluate

    corpus = {
        "documents": [
            {"case_number": "А40-1/2025", "court": "Москва", "text": "Доказательства поставки."},
            {"case_number": "А55-2/2025", "court": "Самара", "text": "Доказательства поставки."},
            {"case_number": "А55-3/2025", "court": "Самара", "text": "Доказательства по поставкам."},
        ],
        "queries": [
            {"id": "inflection", "text": "доказательства поставки",
             "relevant": ["А40-1/2025", "А55-2/2025", "А55-3/2025"]},
            {"id": "court-filter", "text": "доказательства поставки", "court": "Самара",
             "relevant": ["А55-2/2025"]},
        ],
    }

    report = evaluate(corpus)

    assert report["queries"] == [
        {"query_id": "inflection", "returned": 2, "precision_at_5": 2 / 5, "recall_at_10": 2 / 3},
        {"query_id": "court-filter", "returned": 1, "precision_at_5": 1 / 5, "recall_at_10": 1},
    ]


def test_ranked_search_benchmark_applies_top_five_and_top_ten_cutoffs():
    from scripts.benchmark_ranked_search import evaluate

    corpus = {
        "documents": [
            {"case_number": f"А40-{index}/2025", "court": "", "text": "Поставка"}
            for index in range(100, 112)
        ],
        "queries": [{"id": "cutoffs", "text": "поставка",
                     "relevant": ["А40-100/2025", "А40-105/2025", "А40-111/2025"]}],
    }

    report = evaluate(corpus)

    assert report["queries"][0]["returned"] == 10
    assert report["macro_precision_at_5"] == 1 / 5
    assert report["macro_recall_at_10"] == 2 / 3
