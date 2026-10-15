"""MVP API contract: authorization and signed-off source metadata remain explicit."""
from io import BytesIO
from zipfile import ZipFile
from fastapi.testclient import TestClient
from judicial_intelligence.api import create_app


def sample_docx():
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>Ссылка на ст. 54.1 НК РФ.</w:t></w:r></w:p></w:body></w:document>'
    )
    result = BytesIO()
    with ZipFile(result, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return result.getvalue()


def test_authenticated_upload_and_case_timeline(tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db"), api_key="secret"))
    assert client.post("/v1/evidence-files").status_code == 401
    h = {"X-API-Key":"secret"}
    assert client.post("/v1/cases",headers=h,json={"case_number":"А40-123/2025"}).status_code == 201
    resp = client.post(
        "/v1/evidence-files", headers=h, data={"case_number":"А40-123/2025",
                                               "source_kind":"user_provided"},
        files={"file":("act.docx", sample_docx(),
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["verification_status"] == "unverified_user_input"
    file_id = resp.json()["id"]
    report = client.get("/v1/evidence-report",params={"case_number":"А40-123/2025"},headers=h)
    assert report.status_code == 200
    assert report.json()["mentions"][0]["file_id"] == file_id
    act = client.post("/v1/acts", headers=h, json={
        "case_number":"А40-123/2025", "court":"Арбитражный суд",
        "act_date":"2025-01-20","instance":"first","act_type":"решение",
        "linked_file_id":file_id,
    })
    assert act.status_code == 201,act.text
    timeline = client.get("/v1/timeline",headers=h,params={"case_number":"А40-123/2025"})
    assert timeline.status_code == 200
    assert timeline.json()["finality_verified"] is False
    assert len(timeline.json()["acts"]) == 1


def test_reject_invalid_source_and_bad_file(tmp_path):
    client=TestClient(create_app(str(tmp_path / "errors.db"),api_key="secret"))
    h={"X-API-Key":"secret"}
    client.post("/v1/cases",headers=h,json={"case_number":"А40-123/2025"})
    resp=client.post("/v1/evidence-files",headers=h,data={
        "case_number":"А40-123/2025","source_kind":"user_provided"
    },files={"file":("fake.pdf",b"not a pdf","application/pdf")})
    assert resp.status_code == 422
    assert client.get("/v1/evidence-report",params={"case_number":"А40-123/2025"}).status_code == 401


def test_dated_norm_search(tmp_path):
    c = TestClient(create_app(str(tmp_path / "norm.db"),api_key="secret"))
    h={"X-API-Key":"secret"}
    payload={"norm_id":"НК РФ:54.1","text":"Текст пользователя","valid_from":"2025-01-01",
             "source_url":"https://example.org/official"}
    assert c.post("/v1/norms",headers=h,json=payload).status_code == 201
    assert c.get("/v1/norms",headers=h,params={"norm_id":"НК РФ:54.1",
                                                 "on_date":"2024-01-01"}).json()["versions"] == []
    results=c.get("/v1/norms",headers=h,params={"norm_id":"НК РФ:54.1",
                                                 "on_date":"2025-02-01"}).json()
    assert results["versions"][0]["verification_status"] == "unverified_user_input"
