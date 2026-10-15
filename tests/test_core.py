import hashlib
import pytest
from judicial_intelligence.core import normalize_case_number, fingerprint, extract_articles

def test_case_cyrillic_and_latin_normalize():
    assert normalize_case_number(" A40-000123/2025 ") == "А40-123/2025"
    assert normalize_case_number("А40–123/2025") == "А40-123/2025"

@pytest.mark.parametrize("value", ["", "A-1/2025", "40-1/2025", "A40/1/2025", "A40-1/2050"])
def test_invalid_case(value):
    with pytest.raises(ValueError):
        normalize_case_number(value)

def test_literal_mentions_and_offset():
    text = "Стороны сослались на ст. 54.1 НК РФ. Суд применимость не установил."
    extracted = extract_articles(text)
    assert len(extracted) == 1
    item = extracted[0]
    assert item["article"] == "54.1"
    assert text[item["offset_start"]:item["offset_end"]] == item["quote"]
    assert item["classification"] == "literal_reference_only"

def test_no_fabrication():
    assert extract_articles("Суд отказал в иске; ссылки на НК нет.") == []

def test_exact_bytes_digest():
    assert fingerprint("текст") == hashlib.sha256("текст".encode()).hexdigest()
