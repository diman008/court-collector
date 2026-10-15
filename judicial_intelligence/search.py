"""Local SQLite FTS5 index of authorized imported text and original-page references.

Indexes only local files and text already present in the user's SQLite database.
No network access, embeddings, LLM calls or third-party processing.
"""
from __future__ import annotations

import re
import sqlite3

from .core import normalize_case_number
from .source_checks import ReviewStore


def safe_fts_query(value: str) -> str:
    """Convert untrusted input into quoted FTS5 terms, never FTS operators."""
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise ValueError("Search query must be 1-160 characters")
    tokens = re.findall(r"[^\W_]+", value, re.UNICODE)
    if not tokens or len(tokens) > 12:
        raise ValueError("Search must have between 1 and 12 words/numbers")
    return " AND ".join('"' + token.replace('"', '""') + '"' for token in tokens)


class SearchStore(ReviewStore):
    def __init__(self, path: str):
        super().__init__(path)
        with self.connect() as db:
            try:
                db.executescript("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS judicial_fts USING fts5(
                        case_number UNINDEXED,
                        source_type UNINDEXED,
                        source_id UNINDEXED,
                        location_index UNINDEXED,
                        text_content,
                        tokenize='unicode61 remove_diacritics 2'
                    );
                    CREATE TRIGGER IF NOT EXISTS fts_evidence_add AFTER INSERT ON evidence_segments
                    BEGIN
                        INSERT INTO judicial_fts(case_number,source_type,source_id,location_index,text_content)
                        SELECT f.case_number,'evidence_file',new.file_id,new.segment_index,new.text_content
                        FROM evidence_files f WHERE f.id=new.file_id;
                    END;
                    CREATE TRIGGER IF NOT EXISTS fts_evidence_remove AFTER DELETE ON evidence_segments
                    BEGIN
                        DELETE FROM judicial_fts WHERE source_type='evidence_file'
                            AND source_id=old.file_id AND location_index=old.segment_index;
                    END;
                    CREATE TRIGGER IF NOT EXISTS fts_text_add AFTER INSERT ON documents
                    BEGIN
                        INSERT INTO judicial_fts(case_number,source_type,source_id,location_index,text_content)
                        VALUES(new.case_number,'text_document',new.id,0,new.text_content);
                    END;
                    CREATE TRIGGER IF NOT EXISTS fts_text_remove AFTER DELETE ON documents
                    BEGIN
                        DELETE FROM judicial_fts WHERE source_type='text_document' AND source_id=old.id;
                    END;
                """)
            except sqlite3.OperationalError as exc:
                raise RuntimeError("SQLite with the FTS5 extension is required") from exc
            # Idempotent migration of older v2.x SQLite databases.
            db.execute("""
                INSERT INTO judicial_fts(case_number,source_type,source_id,location_index,text_content)
                SELECT f.case_number,'evidence_file',s.file_id,s.segment_index,s.text_content
                FROM evidence_segments s JOIN evidence_files f ON f.id=s.file_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM judicial_fts x WHERE x.source_type='evidence_file'
                    AND x.source_id=s.file_id AND x.location_index=s.segment_index)
            """)
            db.execute("""
                INSERT INTO judicial_fts(case_number,source_type,source_id,location_index,text_content)
                SELECT d.case_number,'text_document',d.id,0,d.text_content
                FROM documents d
                WHERE NOT EXISTS (
                    SELECT 1 FROM judicial_fts x WHERE x.source_type='text_document'
                    AND x.source_id=d.id)
            """)

    def search_text(self, query: str, *, case_number: str | None = None,
                    court: str | None = None, limit: int = 30) -> dict:
        match = safe_fts_query(query)
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        if court is not None and len(court) > 120:
            raise ValueError("Court filter too long")
        normalized = normalize_case_number(case_number) if case_number else None
        # Reject user FTS syntax by binding an all-quoted term expression.
        sql = """
            SELECT j.case_number,j.source_type,j.source_id,j.location_index,
                   bm25(judicial_fts) AS rank,
                   snippet(judicial_fts,4,'[',']',' … ',18) AS excerpt,
                   CASE WHEN j.source_type='evidence_file' THEN f.file_sha256 ELSE d.sha256 END AS sha256,
                   CASE WHEN j.source_type='evidence_file' THEN f.source_url ELSE d.source_url END AS source_url,
                   CASE WHEN j.source_type='evidence_file' THEN f.verification_status ELSE d.verification_status END AS verification_status,
                   CASE WHEN j.source_type='evidence_file' THEN s.location_kind ELSE 'logical_document' END AS location_kind,
                   c.court AS court
            FROM judicial_fts j
            JOIN cases c ON c.case_number=j.case_number
            LEFT JOIN evidence_files f ON j.source_type='evidence_file' AND f.id=j.source_id
            LEFT JOIN evidence_segments s ON j.source_type='evidence_file'
                 AND s.file_id=j.source_id AND s.segment_index=CAST(j.location_index AS INTEGER)
            LEFT JOIN documents d ON j.source_type='text_document' AND d.id=j.source_id
            WHERE judicial_fts MATCH ?
              AND (? IS NULL OR j.case_number=?)
              AND (? IS NULL OR c.court LIKE ? ESCAPE '\\')
            ORDER BY rank ASC,j.case_number,j.source_id
            LIMIT ?
        """
        escaped = court.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") if court else None
        court_pattern = ("%" + escaped + "%") if escaped else None
        try:
            with self.connect() as db:
                rows = db.execute(sql, (match, normalized, normalized, court_pattern,
                                        court_pattern, limit)).fetchall()
        except sqlite3.OperationalError as exc:
            raise RuntimeError("FTS5 search cannot be executed") from exc
        return {
            "query": query, "search_type": "literal_fulltext_unicode61",
            "results": [{**dict(row), "score": round(-float(row["rank"]), 6)} for row in rows],
            "result_limit": limit, "coverage": "local_imports_only",
            "source_verification": "unverified",
            "warning": "Search hits are literal text, not verified rulings or legal conclusions.",
        }
