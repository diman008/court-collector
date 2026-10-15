"""Evidence-first comparison does NOT certify opposing precedent."""
import pytest
from fastapi.testclient import TestClient
from judicial_intelligence.search import SearchStore
from judicial_intelligence.comparison import compare_cases
from judicial_intelligence.api import create_app


def prepared(path):
    store=SearchStore(path)
    for num in ("А40-123/2025", "А55-456/2025"):
        store.put_case(num)
    store.put_document("А40-123/2025",
                       "Истец сослался на ст. 54.1 НК РФ и ст. 77 НК РФ.",
                       "user_provided")
    store.put_document("А55-456/2025",
                       "Сторона упомянула ст. 54.1 НК РФ и ст. 54 НК РФ.",
                       "user_provided")
    store.add_act("А40-123/2025", court="Условный суд 1",
                  act_date="2025-01-10", instance="first", act_type="решение",
                  reported_result="claim_granted")
    store.add_act("А55-456/2025", court="Условный суд 2",
                  act_date="2025-02-11", instance="first", act_type="решение",
                  reported_result="claim_denied")
    return store


def test_side_by_side_legal_evidence_with_disclaimers(tmp_path):
    db=prepared(str(tmp_path / "compare.db"))
    data=compare_cases(db,"А40-123/2025","А55-456/2025")
    assert data["shared_norm_articles"] == ["54.1"]
    assert data["left_only_norm_articles"] == ["77"]
    assert data["right_only_norm_articles"] == ["54"]
    assert len(data["possibly_different_reported_results"]) == 1
    assert data["possibly_different_reported_results"][0]["verified"] is False
    assert data["opposite_court_position_proven"] is False
    assert data["factual_similarity_assessed"] is False
    assert data["legal_conclusions"] == []
    assert data["left"]["citations"][0]["sha256"]
    assert data["right"]["citations"][0]["quote"]


def test_comparison_rest_and_404(tmp_path):
    path=str(tmp_path / "compare.db")
    prepared(path)
    client=TestClient(create_app(path,api_key="secret"))
    args={"left":"А40-123/2025","right":"А55-456/2025"}
    assert client.get("/v1/compare",params=args).status_code==401
    response=client.get("/v1/compare",params=args,headers={"X-API-Key":"secret"})
    assert response.status_code==200,response.text
    assert response.json()["shared_norm_articles"]==["54.1"]
    assert client.get("/v1/compare",params={**args,"right":"А40-123/2025"},
                      headers={"X-API-Key":"secret"}).status_code==422
    assert client.get("/v1/compare",params={**args,"right":"А66-999/2025"},
                      headers={"X-API-Key":"secret"}).status_code==404
