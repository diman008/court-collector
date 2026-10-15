from fastapi.testclient import TestClient
from judicial_intelligence.api import create_app

def test_auth_fail_closed_and_health(tmp_path):
    client = TestClient(create_app(str(tmp_path / "empty.sqlite3"), api_key=""))
    assert client.get("/health").status_code == 200
    assert client.get("/v1/cases").status_code == 503

def test_v1_workflow(tmp_path):
    client = TestClient(create_app(str(tmp_path / "demo.sqlite3"), api_key="test-key"))
    assert client.get("/v1/cases").status_code == 401
    h = {"X-API-Key": "test-key"}
    response = client.post("/v1/cases", headers=h, json={"case_number": "A40-111/2025"})
    assert response.status_code == 201
    doc = client.post("/v1/cases/А40-111/2025/documents", headers=h, json={
        "text": "Упомянута ст. 54.1 НК РФ без вывода о нарушении.",
        "source_kind": "user_provided",
    })
    assert doc.status_code == 201
    assert doc.json()["verification_status"] == "unverified_user_input"
    report = client.get("/v1/cases/А40-111/2025/report", headers=h)
    assert report.status_code == 200
    assert report.json()["article_mentions"][0]["article"] == "54.1"
    assert report.json()["legal_conclusions"] == []
    assert len(client.get("/v1/cases?q=А40", headers=h).json()["results"]) == 1

def test_bad_input(tmp_path):
    client = TestClient(create_app(str(tmp_path / "bad.sqlite3"), api_key="t"))
    h = {"X-API-Key": "t"}
    assert client.post("/v1/cases", headers=h, json={"case_number": "wrong"}).status_code == 422
    assert client.post("/v1/cases", headers=h, json={"case_number":"A40-1/2025","extra":"no"}).status_code == 422
