"""Read-only, evidence-anchored local dossier. Does not invent legal findings."""
from __future__ import annotations
from .evidence import EvidenceStore
from .core import normalize_case_number


def build_dossier(store: EvidenceStore, case_number: str) -> dict:
    number = normalize_case_number(case_number)
    case = store.get_case(number)
    files = store.list_evidence(number)
    timeline = store.timeline(number)
    evidence = store.evidence_report(number)
    text_report = store.report(number)
    # Do not confuse repeated mentions with distinct acts or legal conclusions.
    file_mentions = evidence["mentions"]
    text_mentions = text_report["article_mentions"]
    norm_articles = sorted({item["article"] for item in file_mentions + text_mentions},
                           key=lambda value: [int(x) for x in value.split(".")])
    uncovered = [f for f in files if not f["source_url"]]
    corrupted = []
    for file in files:
        packet = store.verification_packet(number, file["id"])
        if not packet["stored_bytes_match_sha256"]:
            corrupted.append(file["id"])
    unresolved = []
    if not files and not text_report["documents_count"]:
        unresolved.append("В базе нет загруженных первичных судебных документов.")
    if uncovered:
        unresolved.append("Не у каждого вложения есть ссылка на источник.")
    if corrupted:
        unresolved.append("Контрольная сумма некоторых сохранённых файлов не совпадает.")
    if files or text_report["documents_count"]:
        unresolved.append("Подлинность судебных документов и ЭП не подтверждена независимо.")
    if timeline["acts"]:
        unresolved.append("Даты, инстанции, исходы и вступление актов в силу не подтверждены реестром.")
    return {
        "case": case,
        "counts": {
            "evidence_files": len(files),
            "text_documents": text_report["documents_count"],
            "acts": len(timeline["acts"]),
            "literal_mentions": len(file_mentions) + len(text_mentions),
            "norm_articles": len(norm_articles),
        },
        "norm_articles": norm_articles,
        "evidence_files": files,
        "timeline": timeline,
        "literal_references": [
            {
                "article": item["article"],
                "quote": item["quote"],
                "context": item["context"],
                "source_kind": "file",
                "file_id": item["file_id"],
                "source_url": item["source_url"],
                "sha256": item["file_sha256"],
                "location_kind": item["location_kind"],
                "location_index": item["location_index"],
                "offset_start": item["offset_start"],
                "offset_end": item["offset_end"],
                "verification_status": item["verification_status"],
            }
            for item in file_mentions[:250]
        ] + [
            {
                "article": item["article"],
                "quote": item["quote"],
                "context": item["context"],
                "source_kind": "text",
                "document_id": item["document_id"],
                "source_url": item["source_url"],
                "sha256": item["sha256"],
                "offset_start": item["offset_start"],
                "offset_end": item["offset_end"],
                "verification_status": item["verification_status"],
            }
            for item in text_mentions[:250]
        ],
        "mentions_truncated": len(file_mentions)>250 or len(text_mentions)>250,
        "integrity_failures": corrupted,
        "unresolved_checks": unresolved,
        "source_verification": "unverified",
        "judicial_finality_verified": False,
        "legal_conclusions": [],
        "policy": "Literal matches do not establish a court finding or violation.",
    }
