"""Read-only PRIVATE MCP adapter for an authorized local Judicial Intelligence database.

No internet deployment by default. No tools for writes, scrapers or private accounts.
Requires optional MCP Python SDK v2 and a configured >=32-character API key.
"""
from __future__ import annotations

import os
import secrets

from .evidence import EvidenceStore
from .storage import MissingCase


class HeaderKeyGate:
    """Pure ASGI middleware: reject requests before they reach MCP transport."""

    def __init__(self, app, key: str):
        if not key or len(key) < 32:
            raise RuntimeError("JUDICIAL_MCP_KEY must contain at least 32 characters")
        self.app = app
        self.key = key

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        supplied = headers.get(b"x-api-key", b"").decode("utf-8", errors="replace")
        if not secrets.compare_digest(supplied, self.key):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            body = b"Unauthorized"
            await send({"type": "http.response.start", "status": 401, "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"cache-control", b"no-store"),
            ]})
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def create_server(db_path: str):
    """Create typed read-only tools. Native MCP protocol handled by official SDK."""
    from mcp.server import MCPServer
    store = EvidenceStore(db_path)
    server = MCPServer("Judicial Intelligence — local/private", instructions=(
        "Read-only local evidence; sources and judicial status are unverified. "
        "Do not claim a ruling is final or a violation established. No external lookups."
    ))

    @server.tool()
    def search_local_cases(query: str = "", limit: int = 20) -> dict:
        """Search only the local database; never queries public court websites."""
        if len(query) > 160 or limit < 1 or limit > 30:
            return {"error": "Query too long or limit out of bounds"}
        return {"results": store.list_cases(query, limit), "data_scope": "local_only"}

    @server.tool()
    def case_history(case_number: str) -> dict:
        """Read user-recorded court acts and their unverified procedural status."""
        try:
            return store.timeline(case_number)
        except (ValueError, MissingCase):
            return {"error": "Case not found"}

    @server.tool()
    def case_citations(case_number: str) -> dict:
        """Return literal cited legal provisions with original file hash and location."""
        try:
            report = store.evidence_report(case_number)
            # Return bounded amount of citation context; do not dump originals.
            report["mentions"] = [
                {**item, "context": item["context"][:240]}
                for item in report["mentions"][:100]
            ]
            report["truncated"] = len(store.evidence_report(case_number)["mentions"]) > 100
            return report
        except (ValueError, MissingCase):
            return {"error": "Case not found"}

    @server.tool()
    def local_verification_packet(case_number: str, file_id: str) -> dict:
        """Verify only the integrity of locally stored bytes; signature remains UNCHECKED."""
        try:
            return store.verification_packet(case_number, file_id)
        except (ValueError, MissingCase):
            return {"error": "Case or evidence not found"}

    @server.tool()
    def date_scoped_norms(norm_id: str, as_of: str) -> dict:
        """Read locally entered historical norm text with UNVERIFIED provenance."""
        if len(norm_id) > 150:
            return {"error": "Norm id is too long"}
        try:
            rows = store.norm_at(norm_id, as_of)
            return {"versions": [
                {k: v for k, v in item.items() if k != "text_content"}
                for item in rows[:15]
            ], "verification": "unverified_user_input",
                "note": "Norm text is not returned; check an official legal source."}
        except ValueError:
            return {"error": "Invalid date"}

    @server.tool()
    def official_verification_instructions() -> dict:
        """Manual verification steps; does NOT claim court signature validation."""
        return {
            "verification_status": "not_performed",
            "portal": "https://check.arbitr.ru/",
            "steps": [
                "Find the case and the signed judicial act at the official portal.",
                "Choose the exact act and upload its electronic document.",
                "Upload the electronic signature files requested by that portal.",
                "Start official validation and save the result in approved local records.",
            ],
            "warning": "A SHA-256 match verifies stored bytes, not the judge's electronic signature.",
        }

    return server


def create_private_app(db_path: str | None = None, key: str | None = None):
    """Create a loopback-only ready ASGI app. Caller MUST bind 127.0.0.1."""
    configured = key if key is not None else os.getenv("JUDICIAL_MCP_KEY", "")
    if not configured or len(configured) < 32:
        raise RuntimeError("Set a nonempty JUDICIAL_MCP_KEY of at least 32 characters")
    server = create_server(db_path or os.getenv("JUDICIAL_DB_PATH", "data/judicial.sqlite3"))
    app = server.streamable_http_app(stateless_http=True, json_response=True)
    return HeaderKeyGate(app, configured)


def main():
    import uvicorn
    app = create_private_app()
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("JUDICIAL_MCP_PORT", "8765")))


if __name__ == "__main__":
    main()
