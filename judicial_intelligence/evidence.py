"""Provenance-preserving storage for imported files, court-act claims and norm versions."""
from __future__ import annotations
from datetime import date
import hashlib
import json
from uuid import uuid4
from .core import extract_articles, normalize_case_number
from .ingestion import ExtractedFile, extract_file
from .storage import Database, MissingCase, now


class EvidenceStore(Database):
    def __init__(self, path: str):
        super().__init__(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS evidence_files (
                    id TEXT PRIMARY KEY,
                    case_number TEXT NOT NULL REFERENCES cases(case_number),
                    filename TEXT NOT NULL,
                    file_format TEXT NOT NULL,
                    file_sha256 TEXT NOT NULL,
                    original_bytes BLOB NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_url TEXT,
                    received_at TEXT NOT NULL,
                    verification_status TEXT NOT NULL DEFAULT 'unverified_user_input',
                    pagination_verified INTEGER NOT NULL,
                    warnings TEXT NOT NULL,
                    UNIQUE(case_number,file_sha256)
                );
                CREATE TABLE IF NOT EXISTS evidence_segments (
                    file_id TEXT NOT NULL REFERENCES evidence_files(id),
                    segment_index INTEGER NOT NULL,
                    location_kind TEXT NOT NULL,
                    text_content TEXT NOT NULL,
                    PRIMARY KEY(file_id,segment_index)
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence_files(case_number);
                CREATE TABLE IF NOT EXISTS court_acts (
                    id TEXT PRIMARY KEY,
                    case_number TEXT NOT NULL REFERENCES cases(case_number),
                    court TEXT NOT NULL,
                    act_date TEXT NOT NULL,
                    instance TEXT NOT NULL,
                    act_type TEXT NOT NULL,
                    reported_result TEXT NOT NULL DEFAULT 'not_assessed',
                    linked_file_id TEXT REFERENCES evidence_files(id),
                    prior_act_id TEXT REFERENCES court_acts(id),
                    relation_kind TEXT NOT NULL DEFAULT 'unconfirmed',
                    verification_status TEXT NOT NULL DEFAULT 'unverified_user_input',
                    registered_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_acts_case ON court_acts(case_number,act_date);
                CREATE TABLE IF NOT EXISTS norm_versions (
                    id TEXT PRIMARY KEY,
                    norm_id TEXT NOT NULL,
                    text_content TEXT NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT,
                    source_url TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    verification_status TEXT NOT NULL DEFAULT 'unverified_user_input',
                    UNIQUE(norm_id,valid_from,source_url)
                );
            """)

    @staticmethod
    def _file_meta(row) -> dict:
        fields = ("id","case_number","filename","file_format","file_sha256","source_kind",
                  "source_url","received_at","verification_status","pagination_verified","warnings")
        value = {field: row[field] for field in fields}
        value["pagination_verified"] = bool(value["pagination_verified"])
        value["warnings"] = json.loads(value["warnings"])
        return value

    def ingest(self, case_number: str, filename: str, raw: bytes, source_kind: str,
               source_url: str | None = None, *, use_ocr: bool = False) -> dict:
        number = normalize_case_number(case_number)
        self.get_case(number)
        if source_kind not in ("user_provided","official_export","licensed_api"):
            raise ValueError("Unknown source kind")
        extracted = extract_file(filename, raw, use_ocr=use_ocr)
        with self.connect() as db:
            existing = db.execute(
                "SELECT * FROM evidence_files WHERE case_number=? AND file_sha256=?",
                (number, extracted.original_sha256)).fetchone()
            if existing:
                return {**self._file_meta(existing), "duplicate": True}
            identifier = str(uuid4())
            db.execute(
                """INSERT INTO evidence_files(id,case_number,filename,file_format,file_sha256,
                original_bytes,source_kind,source_url,received_at,pagination_verified,warnings)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (identifier, number, filename[:255], extracted.format, extracted.original_sha256,
                 raw, source_kind, source_url, now(), int(extracted.pagination_verified),
                 json.dumps(extracted.warnings, ensure_ascii=False)),
            )
            db.executemany(
                "INSERT INTO evidence_segments(file_id,segment_index,location_kind,text_content) VALUES (?,?,?,?)",
                [(identifier, s.index, s.location_kind, s.text) for s in extracted.segments],
            )
            saved = db.execute("SELECT * FROM evidence_files WHERE id=?", (identifier,)).fetchone()
        return {**self._file_meta(saved), "duplicate": False}

    def list_evidence(self, case_number: str) -> list[dict]:
        number = normalize_case_number(case_number)
        self.get_case(number)
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM evidence_files WHERE case_number=? ORDER BY received_at,id",
                (number,)).fetchall()
        return [self._file_meta(row) for row in rows]

    def evidence_report(self, case_number: str) -> dict:
        number = normalize_case_number(case_number)
        self.get_case(number)
        with self.connect() as db:
            rows = db.execute(
                """SELECT f.id,f.file_sha256,f.source_url,f.verification_status,
                          f.pagination_verified,s.segment_index,s.location_kind,s.text_content
                   FROM evidence_files f JOIN evidence_segments s ON s.file_id=f.id
                   WHERE f.case_number=? ORDER BY f.received_at,f.id,s.segment_index""",
                (number,)).fetchall()
        matches = []
        for row in rows:
            if not row["text_content"].strip():
                continue
            for item in extract_articles(row["text_content"]):
                matches.append({
                    **item, "file_id":row["id"], "file_sha256":row["file_sha256"],
                    "source_url":row["source_url"],"verification_status":row["verification_status"],
                    "location_kind":row["location_kind"],
                    "location_index":row["segment_index"],
                    "pagination_verified":bool(row["pagination_verified"]),
                })
        return {"case_number":number,"mentions":matches,"legal_conclusions":[],
                "analysis_status":"literal_matches_only_unverified",
                "note":"PDF page = physical page in input; DOCX location = logical document, not a page."}

    def add_act(self, case_number: str, *, court: str, act_date: str, instance: str,
                act_type: str, reported_result: str = "not_assessed",
                linked_file_id: str | None = None,
                prior_act_id: str | None = None, relation_kind: str = "unconfirmed") -> dict:
        number = normalize_case_number(case_number)
        self.get_case(number)
        date.fromisoformat(act_date)
        if not court.strip() or not act_type.strip():
            raise ValueError("Court and act type are required")
        if instance not in ("first","appeal","cassation","supreme","other"):
            raise ValueError("Unknown instance")
        if reported_result not in ("not_assessed","claim_granted","claim_denied","partially_granted",
                                   "remanded","terminated","other"):
            raise ValueError("Unknown result")
        if relation_kind not in ("unconfirmed","upholds","reverses","modifies","cites"):
            raise ValueError("Unknown relation")
        if relation_kind != "unconfirmed" and not prior_act_id:
            raise ValueError("Relation requires a prior act")
        with self.connect() as db:
            if linked_file_id:
                ref = db.execute("SELECT case_number FROM evidence_files WHERE id=?", (linked_file_id,)).fetchone()
                if not ref or ref["case_number"] != number:
                    raise ValueError("Linked evidence is missing or belongs to another case")
            if prior_act_id:
                ref = db.execute("SELECT case_number FROM court_acts WHERE id=?", (prior_act_id,)).fetchone()
                if not ref or ref["case_number"] != number:
                    raise ValueError("Prior act is missing or belongs to another case")
            identifier = str(uuid4())
            db.execute(
                """INSERT INTO court_acts(id,case_number,court,act_date,instance,act_type,
                   reported_result,linked_file_id,prior_act_id,relation_kind,registered_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (identifier,number,court,act_date,instance,act_type,reported_result,linked_file_id,
                 prior_act_id,relation_kind,now()),
            )
            record = db.execute("SELECT * FROM court_acts WHERE id=?", (identifier,)).fetchone()
        return dict(record)

    def timeline(self, case_number: str) -> dict:
        number = normalize_case_number(case_number)
        self.get_case(number)
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM court_acts WHERE case_number=? ORDER BY act_date,id",
                (number,)).fetchall()
        return {"case_number":number, "acts":[dict(row) for row in rows],
                "finality_verified":False,
                "note":"Stages/outcomes are unverified user assertions, not registry status."}

    def register_norm(self, norm_id: str, text: str, valid_from: str,
                      source_url: str, valid_to: str | None = None) -> dict:
        begin = date.fromisoformat(valid_from)
        end = date.fromisoformat(valid_to) if valid_to else None
        if end and end < begin:
            raise ValueError("Norm period ends before it starts")
        if not norm_id.strip() or not text.strip() or not source_url.startswith("https://"):
            raise ValueError("Norm text, id and HTTPS source are required")
        identifier = str(uuid4())
        with self.connect() as db:
            db.execute(
                """INSERT INTO norm_versions(id,norm_id,text_content,valid_from,valid_to,source_url,captured_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (identifier,norm_id,text,valid_from,valid_to,source_url,now()),
            )
            record = db.execute("SELECT * FROM norm_versions WHERE id=?", (identifier,)).fetchone()
        return dict(record)

    def norm_at(self, norm_id: str, on_date: str) -> list[dict]:
        date.fromisoformat(on_date)
        with self.connect() as db:
            rows = db.execute(
                """SELECT * FROM norm_versions WHERE norm_id=? AND valid_from<=?
                   AND (valid_to IS NULL OR valid_to>=?) ORDER BY valid_from DESC""",
                (norm_id,on_date,on_date)).fetchall()
        return [dict(row) for row in rows]

    def verification_packet(self, case_number: str, file_id: str) -> dict:
        """Local byte-integrity check + unverified official signature review instructions."""
        number = normalize_case_number(case_number)
        self.get_case(number)
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM evidence_files WHERE case_number=? AND id=?",
                (number, file_id),
            ).fetchone()
        if row is None:
            raise ValueError("File not found within this case")
        observed = hashlib.sha256(row["original_bytes"]).hexdigest()
        return {
            "case_number": number,
            "file_id": row["id"],
            "filename": row["filename"],
            "original_sha256": row["file_sha256"],
            "stored_bytes_match_sha256": observed == row["file_sha256"],
            "claimed_source_url": row["source_url"],
            "source_claim": row["source_kind"],
            "received_at": row["received_at"],
            "source_verification_status": row["verification_status"],
            "signature_verification_status": "not_performed",
            "judicial_finality_verified": False,
            "official_signature_check_url": "https://check.arbitr.ru/",
            "instructions": [
                "Identify the precise act and case number on the official portal.",
                "Upload the exact authorized electronic document and separate signature files.",
                "Run the official check, review the output and retain evidence locally.",
                "Compare the exact checked original bytes with original_sha256.",
                "Have an authorized reviewer confirm the result and the case timeline.",
            ],
            "warning": "Matching a stored SHA-256 does not prove the court signed this act.",
        }
