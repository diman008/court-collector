"""Machine-readable source inventory. Entries are NOT approval to scrape."""
from __future__ import annotations


SOURCES = (
    {
        "id": "kad",
        "name": "Картотека арбитражных дел",
        "url": "https://kad.arbitr.ru/",
        "data_type": "arbitration_case_card",
        "access_type": "human_facing_website",
        "automatic_access_verified": False,
        "connector_enabled": False,
        "rights_review_status": "pending",
        "allowed_workflow_now": "human_read_and_authorized_local_import",
        "restrictions": "Terms, quotas, CAPTCHA and integration rights must be verified separately.",
    },
    {
        "id": "ras",
        "name": "Банк решений арбитражных судов",
        "url": "https://ras.arbitr.ru/",
        "data_type": "arbitration_court_acts",
        "access_type": "human_facing_website",
        "automatic_access_verified": False,
        "connector_enabled": False,
        "rights_review_status": "pending",
        "allowed_workflow_now": "human_read_and_authorized_local_import",
        "restrictions": "No documented automatic access has been approved for this project.",
    },
    {
        "id": "check",
        "name": "Официальная проверка электронной подписи судебного акта",
        "url": "https://check.arbitr.ru/",
        "data_type": "document_electronic_signature",
        "access_type": "human_facing_website",
        "automatic_access_verified": False,
        "connector_enabled": False,
        "rights_review_status": "pending",
        "allowed_workflow_now": "human_check_only",
        "restrictions": "SHA-256 of local bytes is not a judge signature validation.",
    },
    {
        "id": "pravo",
        "name": "Официальный интернет-портал правовой информации",
        "url": "https://pravo.gov.ru/",
        "data_type": "normative_legal_acts",
        "access_type": "human_facing_website",
        "automatic_access_verified": False,
        "connector_enabled": False,
        "rights_review_status": "pending",
        "allowed_workflow_now": "human_check_only",
        "restrictions": "Historical revisions and effective dates need independent verification.",
    },
)


def list_official_sources() -> dict:
    return {
        "sources": [dict(source) for source in SOURCES],
        "catalog_scope": "informational_only",
        "automated_case_collection": "disabled",
        "note": "Source availability and technical connectivity do not establish rights to bulk automated access.",
    }
