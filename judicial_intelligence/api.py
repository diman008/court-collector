"""Authentication required for all judicial data; no live third-party requests."""
import os
import secrets
from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from . import __version__
from .core import MAX_CHARS
from .storage import MissingCase
from .evidence import EvidenceStore
from .ingestion import MAX_FILE_BYTES, ImportErrorValue


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseInput(StrictModel):
    case_number: str = Field(min_length=8, max_length=40)
    title: str = Field(default="", max_length=400)
    court: str = Field(default="", max_length=250)
    case_date: date | None = None


class DocumentInput(StrictModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)
    source_kind: Literal["user_provided", "official_export", "licensed_api"]
    source_url: HttpUrl | None = None
    published_at: date | None = None



class ActInput(StrictModel):
    case_number: str = Field(min_length=8, max_length=40)
    court: str = Field(min_length=1, max_length=250)
    act_date: date
    instance: Literal["first", "appeal", "cassation", "supreme", "other"]
    act_type: str = Field(min_length=1, max_length=150)
    reported_result: Literal["not_assessed","claim_granted","claim_denied",
                             "partially_granted","remanded","terminated","other"] = "not_assessed"
    linked_file_id: str | None = None
    prior_act_id: str | None = None
    relation_kind: Literal["unconfirmed","upholds","reverses","modifies","cites"] = "unconfirmed"


class NormInput(StrictModel):
    norm_id: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=30000)
    valid_from: date
    valid_to: date | None = None
    source_url: HttpUrl

def create_app(db_path: str | None = None, api_key: str | None = None) -> FastAPI:
    key = api_key if api_key is not None else os.getenv("JUDICIAL_API_KEY", "")
    db = EvidenceStore(db_path or os.getenv("JUDICIAL_DB_PATH", "data/judicial.sqlite3"))
    app = FastAPI(title="Judicial Intelligence", version=__version__, docs_url=None, redoc_url=None)

    def authenticate(x_api_key: str | None = Header(default=None)) -> None:
        if not key:
            raise HTTPException(status_code=503, detail="API key not configured")
        if not x_api_key or not secrets.compare_digest(key, x_api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "external_connectors": "disabled"}

    @app.post("/v1/cases", status_code=201, dependencies=[Depends(authenticate)])
    def put_case(payload: CaseInput):
        try:
            return db.put_case(payload.case_number, payload.title, payload.court,
                               str(payload.case_date) if payload.case_date else None)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/cases", dependencies=[Depends(authenticate)])
    def search_cases(q: str = Query("", max_length=160), limit: int = Query(30, ge=1, le=100)):
        return {"results": db.list_cases(q, limit)}

    @app.get("/v1/case", dependencies=[Depends(authenticate)])
    def get_case(case_number: str):
        try:
            return db.get_case(case_number)
        except (MissingCase, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc

    @app.post("/v1/documents", status_code=201, dependencies=[Depends(authenticate)])
    def put_document(case_number: str, payload: DocumentInput):
        try:
            return db.put_document(case_number, payload.text, payload.source_kind,
                                   str(payload.source_url) if payload.source_url else None,
                                   str(payload.published_at) if payload.published_at else None)
        except MissingCase as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/documents", dependencies=[Depends(authenticate)])
    def list_documents(case_number: str):
        try:
            return {"documents": db.documents(case_number)}
        except (MissingCase, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc

    @app.get("/v1/report", dependencies=[Depends(authenticate)])
    def get_report(case_number: str):
        try:
            return db.report(case_number)
        except (MissingCase, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc


    @app.post("/v1/evidence-files", status_code=201, dependencies=[Depends(authenticate)])
    async def upload_evidence(case_number: str = Form(...),
                              source_kind: Literal["user_provided", "official_export", "licensed_api"] = Form("user_provided"),
                              source_url: str | None = Form(None),
                              file: UploadFile = File(...)):
        try:
            raw = await file.read(MAX_FILE_BYTES + 1)
            return db.ingest(case_number, file.filename or "", raw, source_kind, source_url)
        except MissingCase as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except (ImportErrorValue, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await file.close()

    @app.get("/v1/evidence-files", dependencies=[Depends(authenticate)])
    def evidence_files(case_number: str):
        try:
            return {"files": db.list_evidence(case_number)}
        except (MissingCase, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc

    @app.get("/v1/evidence-report", dependencies=[Depends(authenticate)])
    def evidence_report(case_number: str):
        try:
            return db.evidence_report(case_number)
        except (MissingCase, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc

    @app.post("/v1/acts", status_code=201, dependencies=[Depends(authenticate)])
    def create_act(payload: ActInput):
        try:
            return db.add_act(payload.case_number, court=payload.court, act_date=str(payload.act_date),
                              instance=payload.instance, act_type=payload.act_type,
                              reported_result=payload.reported_result,
                              linked_file_id=payload.linked_file_id,
                              prior_act_id=payload.prior_act_id, relation_kind=payload.relation_kind)
        except MissingCase as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/timeline", dependencies=[Depends(authenticate)])
    def timeline(case_number: str):
        try:
            return db.timeline(case_number)
        except (MissingCase, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc

    @app.post("/v1/norms", status_code=201, dependencies=[Depends(authenticate)])
    def create_norm(payload: NormInput):
        try:
            return db.register_norm(payload.norm_id, payload.text, str(payload.valid_from),
                                    str(payload.source_url),
                                    str(payload.valid_to) if payload.valid_to else None)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/norms", dependencies=[Depends(authenticate)])
    def norm_at(norm_id: str = Query(..., max_length=150), on_date: date = Query(...)):
        return {"versions": db.norm_at(norm_id, str(on_date)), "source_verification": "unverified"}

    return app


app = create_app()
