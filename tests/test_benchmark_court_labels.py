"""Regression tests for court-filter relevance labels in ranked search benchmark."""

import pytest

from scripts.benchmark_ranked_search import evaluate


def _corpus(relevant):
    return {
        "documents": [
            {"case_number": "А55-2/2025", "court": "Самара", "text": "Поставка"},
            {"case_number": "А40-1/2025", "court": "Москва", "text": "Поставка"},
        ],
        "queries": [{"id": "filtered", "text": "поставка", "court": "Самара", "relevant": relevant}],
    }


def test_rejects_relevant_case_outside_requested_court():
    with pytest.raises(ValueError, match="outside the requested court"):
        evaluate(_corpus(["А55-2/2025", "А40-1/2025"]))


def test_accepts_relevance_labels_within_requested_court():
    result = evaluate(_corpus(["А55-2/2025"]))
    assert result["queries"][0]["recall_at_10"] == 1.0
