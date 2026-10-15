"""Append-only local assertions of a HUMAN review of a known official source.

Events are human claims, not independently validated signatures or court status.
No network access. URLs MUST match the explicit portal host for the claimed check.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from uuid import uuid4
from .core import normalize_case_number
from .evidence import EvidenceStore
from .storage import now

SOURCES = {
    "kad_casecard": ("kad.arbitr.ru",),
    "ras_decision": ("ras.arbitr.ru",),
    "electronic_signature": ("check.arbitr.ru",),
    "legal_text": ("pravo.gov.ru",),
}
RESULTS = {"match_claimed", "mismatch_claimed", "inconclusive"}


def validated_url(source_type: str, url: str) -> str:
    if source_type not in SOURCES:
        raise ValueError("Unknown official source type")
    if not url or len(url) > 1200:
        raise ValueError("Missing or overly long official source URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid source URL") from exc
    if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443):
        raise ValueError("Official source must be HTTPS without credentials/custom port")
    if parsed.hostname not in SOURCES[source_type]:
        raise ValueError("Source URL host does not match the official source type")
    return url


class ReviewStore(EvidenceStore):
    def __init__(self, path: str):
        super().__init__(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS manual_source_checks (
                    id TEXT PRIMARY KEY,
                    case_number TEXT NOT NULL REFERENCES cases(case_number),
                    file_id TEXT REFERENCES evidence_files(id),
                    file_sha256_at_review TEXT,
                    source_type TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    claimed_result TEXT NOT NULL,
                    reviewer_alias TEXT NOT NULL,
                    reviewer_note TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    independent_verification TEXT NOT NULL DEFAULT 'not_performed'
                );
                CREATE INDEX IF NOT EXISTS idx_manual_reviews_case
                  ON manual_source_checks(case_number,recorded_at);
            """)

    def record_source_check(
        self,
        case_number: str,
        *,
        source_type: str,
        source_url: str,
        claimed_result: str,
        reviewer_alias: str,
        reviewer_note: str = "",
        file_id: str | None = None,
    ) -> dict:
        number = normalize_case_number(case_number)
        self.get_case(number)
        address = validated_url(source_type, source_url)
        if claimed_result not in RESULTS:
            raise ValueError("Unknown review result")
        reviewer_alias = reviewer_alias.strip()
        if not reviewer_alias or len(reviewer_alias) > 100:
            raise ValueError("Reviewer alias must be 1-100 characters")
        if len(reviewer_note) > 500:
            raise ValueError("Reviewer note too long")
        with self.connect() as db:
            evidence_sha = None
            if file_id is not None:
                row = db.execute(
                    "SELECT case_number,file_sha256 FROM evidence_files WHERE id=?",
                    (file_id,),
                ).fetchone()
                if row is None or row["case_number"] != number:
                    raise ValueError("File does not exist within the case")
                evidence_sha = row["file_sha256"]
            identifier = str(uuid4())
            db.execute(
                """INSERT INTO manual_source_checks
                (id,case_number,file_id,file_sha256_at_review,source_type,source_url,
                 claimed_result,reviewer_alias,reviewer_note,recorded_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (identifier,number,file_id,evidence_sha,source_type,address,
                 claimed_result,reviewer_alias,reviewer_note,now()),
            )
            return dict(db.execute(
                "SELECT * FROM manual_source_checks WHERE id=?",
                (identifier,),
            ).fetchone())

    def list_source_checks(self, case_number: str) -> list[dict]:
        number = normalize_case_number(case_number)
        self.get_case(number)
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM manual_source_checks WHERE case_number=? ORDER BY recorded_at DESC,id DESC LIMIT 200",
                (number,),
            ).fetchall()
        return [dict(row) for row in rows]
