"""Authentication required for all judicial data; no live third-party requests."""
import os
import secrets
from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from . import __version__
from .core import MAX_CHARS
from .storage import Database, MissingCase


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


def create_app(db_path: str | None = None, api_key: str | None = None) -> FastAPI:
    key = api_key if api_key is not None else os.getenv("JUDICIAL_API_KEY", "")
    db = Database(db_path or os.getenv("JUDICIAL_DB_PATH", "data/judicial.sqlite3"))
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

    return app


app = create_app()
