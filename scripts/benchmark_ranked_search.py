"""Score the existing SQLite FTS5 search on a local, adjudicated text corpus."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from judicial_intelligence.core import normalize_case_number
from judicial_intelligence.search import SearchStore


def evaluate(corpus):
    with TemporaryDirectory() as directory:
        store = SearchStore(str(Path(directory) / "benchmark.db"))
        cases = set()
        for document in corpus["documents"]:
            number = normalize_case_number(document["case_number"])
            if number in cases:
                raise ValueError("Use exactly one text per case in the benchmark")
            cases.add(number)
            store.put_case(number, court=document["court"])
            store.put_document(number, document["text"], "user_provided")

        rows = []
        for query in corpus["queries"]:
            relevant = {normalize_case_number(number) for number in query["relevant"]}
            if not relevant or not relevant <= cases:
                raise ValueError("Each query needs relevant cases from the benchmark corpus")
            matches = store.search_text(query["text"], court=query.get("court"), limit=10)
            ranked = [item["case_number"] for item in matches["results"]]
            rows.append({
                "query_id": query["id"],
                "returned": len(ranked),
                "precision_at_5": len(relevant.intersection(ranked[:5])) / 5,
                "recall_at_10": len(relevant.intersection(ranked)) / len(relevant),
            })

    if not rows:
        raise ValueError("Provide at least one labeled query")
    return {
        "cases": len(cases),
        "queries": rows,
        "macro_precision_at_5": sum(row["precision_at_5"] for row in rows) / len(rows),
        "macro_recall_at_10": sum(row["recall_at_10"] for row in rows) / len(rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="Local JSON with documents and labeled queries")
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(corpus), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
