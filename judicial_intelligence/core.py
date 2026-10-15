"""Deterministic, source-anchored extraction. Not legal advice."""
import hashlib
import re
from datetime import date

CASE_RE = re.compile(r"^[АAаa]\s*(\d{1,3})\s*[-–—]\s*(\d{1,10})\s*/\s*((?:19|20)\d{2})$")
ARTICLE_RE = re.compile(
    r"(?<!\w)(?:статья|ст\.)\s*(\d{1,3}(?:\.\d+)?)\s*(?:НК\s*РФ|Налогового\s+кодекса(?:\s+РФ)?)",
    re.IGNORECASE,
)
MAX_CHARS = 200_000


def normalize_case_number(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Case number must be a string")
    match = CASE_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError("Expected arbitration case number, e.g. А40-12345/2025")
    court, serial, year = match.groups()
    if int(year) > date.today().year + 1:
        raise ValueError("Implausible future year")
    return f"А{int(court)}-{int(serial)}/{year}"


def validate_text(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Document text is empty")
    if len(text) > MAX_CHARS:
        raise ValueError("Document text too large")


def fingerprint(text: str) -> str:
    validate_text(text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_articles(text: str) -> list[dict]:
    """Only literal mentions, with offsets in the original source text."""
    validate_text(text)
    mentions = []
    for match in ARTICLE_RE.finditer(text):
        start, end = match.span()
        mentions.append({
            "article": match.group(1),
            "quote": match.group(0),
            "offset_start": start,
            "offset_end": end,
            "context": text[max(0, start - 90):min(len(text), end + 90)],
            "classification": "literal_reference_only",
        })
    return mentions
