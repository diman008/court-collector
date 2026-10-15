"""Offline processing without a remote service or key."""
import argparse
import json
import os
from .adapters import LocalTextExport
from .storage import Database

def main():
    parser = argparse.ArgumentParser(prog="judicial-intelligence")
    parser.add_argument("--db", default=os.getenv("JUDICIAL_DB_PATH", "data/judicial.sqlite3"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("add-case")
    p.add_argument("number"); p.add_argument("--court", default=""); p.add_argument("--title", default="")
    p = sub.add_parser("import-txt")
    p.add_argument("number"); p.add_argument("filename"); p.add_argument("--source-url")
    p = sub.add_parser("report"); p.add_argument("number")
    args = parser.parse_args()
    store = Database(args.db)
    if args.command == "add-case":
        result = store.put_case(args.number, args.title, args.court)
    elif args.command == "import-txt":
        document = LocalTextExport().load(args.filename)
        result = store.put_document(args.number, document.text, document.source_kind, args.source_url)
    else:
        result = store.report(args.number)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
