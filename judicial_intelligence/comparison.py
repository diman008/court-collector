"""Deterministic, evidence-anchored comparison of TWO locally imported cases.

No LLM inference, finding of similar factual circumstances, or determination
of opposite judicial precedent. Stage results are user claims until verified.
"""
from __future__ import annotations

from .analytics import build_dossier
from .core import normalize_case_number
from .evidence import EvidenceStore


def compare_cases(store: EvidenceStore, left_number: str, right_number: str) -> dict:
    left = normalize_case_number(left_number)
    right = normalize_case_number(right_number)
    if left == right:
        raise ValueError("Two different case numbers are required")
    a = build_dossier(store, left)
    b = build_dossier(store, right)
    a_norms, b_norms = set(a["norm_articles"]), set(b["norm_articles"])
    reported_a = {(x["instance"], x["reported_result"]) for x in a["timeline"]["acts"]}
    reported_b = {(x["instance"], x["reported_result"]) for x in b["timeline"]["acts"]}
    opposite_pairs = {
        frozenset(("claim_granted", "claim_denied")),
        frozenset(("claim_granted", "partially_granted")),
        frozenset(("claim_denied", "partially_granted")),
    }
    # This is a mechanical comparison of labels, NOT a finding of contradictory law.
    conflicting_claims = []
    for inst_a, result_a in sorted(reported_a):
        for inst_b, result_b in sorted(reported_b):
            if inst_a == inst_b and frozenset((result_a, result_b)) in opposite_pairs:
                conflicting_claims.append({
                    "instance": inst_a,
                    "left_claimed_result": result_a,
                    "right_claimed_result": result_b,
                    "verified": False,
                })
    return {
        "left_case": left, "right_case": right,
        "shared_norm_articles": sorted(a_norms & b_norms),
        "left_only_norm_articles": sorted(a_norms - b_norms),
        "right_only_norm_articles": sorted(b_norms - a_norms),
        "possibly_different_reported_results": conflicting_claims,
        "left": {
            "case": a["case"], "counts": a["counts"],
            "acts": a["timeline"]["acts"][:40],
            "citations": a["literal_references"][:12],
            "unresolved_checks": a["unresolved_checks"],
        },
        "right": {
            "case": b["case"], "counts": b["counts"],
            "acts": b["timeline"]["acts"][:40],
            "citations": b["literal_references"][:12],
            "unresolved_checks": b["unresolved_checks"],
        },
        "source_verification": "unverified",
        "opposite_court_position_proven": False,
        "factual_similarity_assessed": False,
        "legal_conclusions": [],
        "warning": "Matching cited article and differing entered result labels do not establish precedent, factual similarity, or legally opposite rulings.",
    }
