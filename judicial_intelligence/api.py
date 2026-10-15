"""Authentication required for all judicial data; no live third-party requests."""
import os
import secrets
from datetime import date
from importlib.resources import files
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from . import __version__
from .core import MAX_CHARS
from .storage import MissingCase
from .evidence import EvidenceStore
from .analytics import build_dossier
from .search import SearchStore
from .comparison import compare_cases
from .source_registry import list_official_sources
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

class ReviewInput(StrictModel):
    case_number: str = Field(min_length=8,max_length=40)
    file_id: str | None = Field(default=None,max_length=90)
    source_type: Literal["kad_casecard","ras_decision","electronic_signature","legal_text"]
    source_url: HttpUrl
    claimed_result: Literal["match_claimed","mismatch_claimed","inconclusive"]
    reviewer_alias: str = Field(min_length=1,max_length=100)
    reviewer_note: str = Field(default="",max_length=500)


def create_app(db_path: str | None = None, api_key: str | None = None) -> FastAPI:
    key = api_key if api_key is not None else os.getenv("JUDICIAL_API_KEY", "")
    db = SearchStore(db_path or os.getenv("JUDICIAL_DB_PATH", "data/judicial.sqlite3"))
    app = FastAPI(title="Judicial Intelligence", version=__version__, docs_url=None, redoc_url=None)

    def authenticate(x_api_key: str | None = Header(default=None)) -> None:
        if not key:
            raise HTTPException(status_code=503, detail="API key not configured")
        if not x_api_key or not secrets.compare_digest(key, x_api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "external_connectors": "disabled"}

    def _asset(filename: str, mime: str) -> Response:
        content = files("judicial_intelligence").joinpath("assets", filename).read_bytes()
        response = Response(content=content, media_type=mime)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; connect-src 'self'; script-src 'self'; "
            "style-src 'self'; img-src 'self'; form-action 'self'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    @app.get("/analyst", include_in_schema=False)
    def analyst_page():
        # Static app shell only: no case data or keys are interpolated.
        return _asset("analyst.html", "text/html; charset=utf-8")

    @app.get("/analyst.js", include_in_schema=False)
    def analyst_script():
        return _asset("analyst.js", "text/javascript; charset=utf-8")

    @app.get("/analyst.css", include_in_schema=False)
    def analyst_styles():
        return _asset("analyst.css", "text/css; charset=utf-8")

    @app.get("/v1/dossier", dependencies=[Depends(authenticate)])
    def case_dossier(case_number: str = Query(..., max_length=40)):
        try:
            return build_dossier(db, case_number)
        except (MissingCase, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc

    @app.get("/v1/sources", dependencies=[Depends(authenticate)])
    def source_registry():
        return list_official_sources()

    @app.get("/v1/fulltext", dependencies=[Depends(authenticate)])
    def fulltext_search(q: str = Query(..., min_length=1, max_length=160),
                        case_number: str | None = Query(None,max_length=40),
                        court: str | None = Query(None,max_length=120),
                        limit: int = Query(30,ge=1,le=100)):
        try:
            return db.search_text(q,case_number=case_number,court=court,limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc

    @app.get("/v1/compare", dependencies=[Depends(authenticate)])
    def compare_two_cases(left: str = Query(...,max_length=40),
                          right: str = Query(...,max_length=40)):
        try:
            return compare_cases(db,left,right)
        except MissingCase as exc:
            raise HTTPException(status_code=404,detail="Case not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc

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

    @app.get("/v1/verification-packet", dependencies=[Depends(authenticate)])
    def verification_packet(case_number: str, file_id: str):
        try:
            return db.verification_packet(case_number, file_id)
        except (ValueError, MissingCase) as exc:
            raise HTTPException(status_code=404, detail="Case or evidence not found") from exc

    @app.post("/v1/reviews", status_code=201, dependencies=[Depends(authenticate)])
    def record_manual_review(payload: ReviewInput):
        try:
            return db.record_source_check(
                payload.case_number,
                file_id=payload.file_id,
                source_type=payload.source_type,
                source_url=str(payload.source_url),
                claimed_result=payload.claimed_result,
                reviewer_alias=payload.reviewer_alias,
                reviewer_note=payload.reviewer_note,
            )
        except MissingCase as exc:
            raise HTTPException(status_code=404, detail="Case not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/reviews", dependencies=[Depends(authenticate)])
    def list_manual_reviews(case_number: str = Query(...,max_length=40)):
        try:
            return {
                "records": db.list_source_checks(case_number),
                "verification_scope": "user_assertions_only",
            }
        except (MissingCase,ValueError) as exc:
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
