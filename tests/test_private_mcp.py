"""MCP SDK tool registration, read-only behavior and fail-closed ASGI access."""
import asyncio
import json
import pytest
from judicial_intelligence.private_mcp import create_private_app, create_server, HeaderKeyGate
from judicial_intelligence.evidence import EvidenceStore


def test_key_required(tmp_path):
    with pytest.raises(RuntimeError, match="32 characters"):
        create_private_app(str(tmp_path / "cases.db"), key="weak")
    with pytest.raises(RuntimeError, match="32 characters"):
        HeaderKeyGate(lambda *args: None, "")


def test_registered_read_only_tools(tmp_path):
    store = EvidenceStore(str(tmp_path / "cases.db"))
    store.put_case("А40-123/2025")
    server = create_server(str(tmp_path / "cases.db"))
    tools = asyncio.run(server.list_tools())
    names = {x.name for x in tools}
    assert names == {"search_local_cases", "case_history", "case_citations",
                     "date_scoped_norms", "official_verification_instructions",
                     "local_verification_packet", "analyst_case_dossier", "manual_source_review_log"}
    assert not any("write" in name or "upload" in name or "scrape" in name for name in names)
    result = asyncio.run(server.call_tool("search_local_cases", {"query": "А40", "limit": 5}))
    assert not result.is_error
    payload = result.structured_content or json.loads(result.content[0].text)
    assert payload["results"][0]["case_number"] == "А40-123/2025"
    dossier = asyncio.run(server.call_tool("analyst_case_dossier", {"case_number": "А40-123/2025"}))
    summary = dossier.structured_content or json.loads(dossier.content[0].text)
    assert summary["legal_conclusions"] == []
    assert summary["source_verification"] == "unverified"
    reviews = asyncio.run(server.call_tool("manual_source_review_log", {"case_number": "А40-123/2025"}))
    data = reviews.structured_content or json.loads(reviews.content[0].text)
    assert data["verification_scope"] == "user_assertions_only"
    assert data["records"] == []


def test_asgi_http_key_gate():
    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    gate = HeaderKeyGate(inner, "x"*32)
    async def probe(headers):
        messages = []
        async def send(message): messages.append(message)
        async def receive(): return {"type": "http.request", "body": b"", "more_body": False}
        await gate({"type": "http", "headers": headers}, receive, send)
        return messages
    assert asyncio.run(probe([]))[0]["status"] == 401
    assert asyncio.run(probe([(b"x-api-key", b"wrong")]))[0]["status"] == 401
    assert asyncio.run(probe([(b"x-api-key", b"x"*32)]))[0]["status"] == 200
