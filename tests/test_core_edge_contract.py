"""Additional deterministic extraction contract edges.

Run from repository root: python -m pytest -q tests/test_core_edge_contract.py
"""
import pytest

from judicial_intelligence.core import extract_articles, normalize_case_number


def test_unicode_prefix_offsets_remain_python_character_offsets():
    text = "⚖️📄\nСсылка: СТАТЬЯ 54.1 НАЛОГОВОГО КОДЕКСА РФ; далее — ст. 101 НК РФ."
    mentions = extract_articles(text)
    assert [item["article"] for item in mentions] == ["54.1", "101"]
    for item in mentions:
        assert text[item["offset_start"]:item["offset_end"]] == item["quote"]
        assert item["classification"] == "literal_reference_only"


def test_embedded_reference_in_identifier_is_not_evidence():
    assert extract_articles("prefixст. 54.1 НК РФ") == []
    assert [item["article"] for item in extract_articles("ст. 54.1 НК РФ")] == ["54.1"]


def test_case_identifier_does_not_accept_appended_text():
    for value in ("А40-123/2025 дополнительный текст", "А40-123/2025\nА41-1/2025"):
        with pytest.raises(ValueError):
            normalize_case_number(value)
