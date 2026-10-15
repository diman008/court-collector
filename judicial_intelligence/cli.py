"""Offline processing without a remote service or key."""
import argparse
import json
import os
from .adapters import LocalTextExport
from .search import SearchStore
from .comparison import compare_cases

def main():
    parser = argparse.ArgumentParser(prog="judicial-intelligence")
    parser.add_argument("--db", default=os.getenv("JUDICIAL_DB_PATH", "data/judicial.sqlite3"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("add-case")
    p.add_argument("number"); p.add_argument("--court", default=""); p.add_argument("--title", default="")
    p = sub.add_parser("import-txt")
    p.add_argument("number"); p.add_argument("filename"); p.add_argument("--source-url")
    p = sub.add_parser("import-file")
    p.add_argument("number"); p.add_argument("filename"); p.add_argument("--source-url"); p.add_argument("--ocr", action="store_true", help="Offline OCR of textless PDF pages; requires optional OCR tools")
    p = sub.add_parser("evidence-report"); p.add_argument("number")
    p = sub.add_parser("timeline"); p.add_argument("number")
    p = sub.add_parser("fulltext")
    p.add_argument("query"); p.add_argument("--case-number"); p.add_argument("--court")
    p.add_argument("--limit",type=int,default=30)
    p = sub.add_parser("compare")
    p.add_argument("left"); p.add_argument("right")
    p = sub.add_parser("pilot-docling")
    p.add_argument("filename")
    p = sub.add_parser("report"); p.add_argument("number")
    args = parser.parse_args()
    store = SearchStore(args.db)
    if args.command == "add-case":
        result = store.put_case(args.number, args.title, args.court)
    elif args.command == "import-txt":
        document = LocalTextExport().load(args.filename)
        result = store.put_document(args.number, document.text, document.source_kind, args.source_url)
    elif args.command == "import-file":
        from pathlib import Path
        path = Path(args.filename)
        result = store.ingest(args.number, path.name, path.read_bytes(), "user_provided", args.source_url, use_ocr=args.ocr)
    elif args.command == "evidence-report":
        result = store.evidence_report(args.number)
    elif args.command == "timeline":
        result = store.timeline(args.number)
    elif args.command == "fulltext":
        result = store.search_text(args.query,case_number=args.case_number,court=args.court,
                                   limit=args.limit)
    elif args.command == "compare":
        result = compare_cases(store,args.left,args.right)
    elif args.command == "pilot-docling":
        from pathlib import Path
        from .docling_pilot import pilot_docling
        path = Path(args.filename)
        parsed = pilot_docling(path.name,path.read_bytes())
        result = {"sha256": parsed.original_sha256, "format": parsed.format,
                  "pagination_verified": parsed.pagination_verified,
                  "warnings": parsed.warnings, "segments": [
                    {"index":p.index,"location_kind":p.location_kind,
                     "characters":len(p.text),"preview":p.text[:120]}
                    for p in parsed.segments
                  ]}
    else:
        result = store.report(args.number)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
