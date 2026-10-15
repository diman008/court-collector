"""SQLite evidence store; source hashes and exact offsets remain attached."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .core import normalize_case_number, fingerprint, extract_articles


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissingCase(LookupError):
    pass


class Database:
    def __init__(self, path: str):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS cases (
                    case_number TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    court TEXT NOT NULL DEFAULT '',
                    case_date TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    case_number TEXT NOT NULL REFERENCES cases(case_number),
                    source_kind TEXT NOT NULL,
                    source_url TEXT,
                    published_at TEXT,
                    retrieved_at TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    text_content TEXT NOT NULL,
                    verification_status TEXT NOT NULL DEFAULT 'unverified_user_input',
                    UNIQUE(case_number,sha256)
                );
                CREATE INDEX IF NOT EXISTS idx_docs_case ON documents(case_number);
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def put_case(self, case_number: str, title: str = "",
                 court: str = "", case_date: str | None = None) -> dict:
        number = normalize_case_number(case_number)
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO cases(case_number,title,court,case_date,created_at) VALUES(?,?,?,?,?)",
                       (number, title, court, case_date, now()))
        return self.get_case(number)

    def get_case(self, case_number: str) -> dict:
        number = normalize_case_number(case_number)
        with self.connect() as db:
            row = db.execute("SELECT * FROM cases WHERE case_number=?", (number,)).fetchone()
        if row is None:
            raise MissingCase(number)
        return dict(row)

    def list_cases(self, query: str = "", limit: int = 30) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid limit")
        escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM cases WHERE case_number LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' OR court LIKE ? ESCAPE '\\' ORDER BY created_at DESC LIMIT ?",
                (pattern, pattern, pattern, limit),
            ).fetchall()
        return [dict(x) for x in rows]

    def put_document(self, case_number: str, text: str, source_kind: str,
                     source_url: str | None = None, published_at: str | None = None) -> dict:
        number = normalize_case_number(case_number)
        digest = fingerprint(text)
        self.get_case(number)
        with self.connect() as db:
            existing = db.execute("SELECT * FROM documents WHERE case_number=? AND sha256=?", (number, digest)).fetchone()
            if existing:
                return {**self._meta(existing), "duplicate": True}
            identifier = str(uuid4())
            db.execute(
                "INSERT INTO documents(id,case_number,source_kind,source_url,published_at,retrieved_at,sha256,text_content) VALUES(?,?,?,?,?,?,?,?)",
                (identifier, number, source_kind, source_url, published_at, now(), digest, text),
            )
            row = db.execute("SELECT * FROM documents WHERE id=?", (identifier,)).fetchone()
        return {**self._meta(row), "duplicate": False}

    @staticmethod
    def _meta(row) -> dict:
        keys = ("id", "case_number", "source_kind", "source_url", "published_at",
                "retrieved_at", "sha256", "verification_status")
        return {key: row[key] for key in keys}

    def documents(self, case_number: str) -> list[dict]:
        number = normalize_case_number(case_number)
        self.get_case(number)
        with self.connect() as db:
            rows = db.execute("SELECT * FROM documents WHERE case_number=? ORDER BY retrieved_at,id", (number,)).fetchall()
        return [self._meta(row) for row in rows]

    def report(self, case_number: str) -> dict:
        number = normalize_case_number(case_number)
        case = self.get_case(number)
        with self.connect() as db:
            rows = db.execute("SELECT * FROM documents WHERE case_number=? ORDER BY retrieved_at,id", (number,)).fetchall()
        mentions = []
        for row in rows:
            for mention in extract_articles(row["text_content"]):
                mentions.append({
                    **mention, "document_id": row["id"], "sha256": row["sha256"],
                    "source_url": row["source_url"], "published_at": row["published_at"],
                    "verification_status": row["verification_status"],
                })
        return {
            "case": case, "documents_count": len(rows), "article_mentions": mentions,
            "analysis_status": "deterministic_extraction_only", "legal_conclusions": [],
            "limitations": [
                "Source documents and metadata are not independently verified.",
                "Article mentions do not prove applicability or establish a violation.",
                "A human must check official decisions, procedural stage and legal version.",
            ],
        }
