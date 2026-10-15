# Reuse decisions / решения по готовым компонентам
Updated 2026-10-15. No third-party repository code has been copied or vendored.

| Area | Reused solution | How used | Important boundary |
|---|---|---|---|
| REST and local analyst UI | [FastAPI](https://fastapi.tiangolo.com/), Pydantic / Starlette | Authenticated local API, bundled assets, request validation and TestClient | Simple API key and localhost are NOT adequate for internet production |
| MCP protocol | [Official MCP Python SDK v2](https://py.sdk.modelcontextprotocol.io/) | Local read-only Streamable HTTP server, tool registration, schema validation | Explicitly private, no public connector or OAuth yet |
| PDF | [pypdf](https://pypdf.readthedocs.io/) | Extract page text and retain original physical page number | Text extraction never verifies signed PDFs |
| Local OCR | [Tesseract OCR](https://github.com/tesseract-ocr/tesseract), pytesseract, pypdfium2 | Optional local OCR of textless PDF pages with strict limits | No external OCR or automatic recognition of all pages |
| Court search guidance | [KAD](https://kad.arbitr.ru/) + Inspector Resources MCP catalog entry `kad` | Manual link and source reference | Catalog metadata only; NOT case retrieval |
| Court electronic signatures | [Electronic Justice signature checker](https://check.arbitr.ru/) | Manual verification workflow and tamper-evident review packet | No signature validation is claimed |
| Judicial decisions | [Arbitration decision bank](https://ras.arbitr.ru/) | Official-site link for manual access | No permission for automatic ingestion established |
| Legal acts | [Official legal portal](https://pravo.gov.ru/) | Manual primary-source link | Effective-date confirmation not automated |
| QA | pytest, FastAPI TestClient, GitHub Actions | Python tests, JavaScript syntax check and Docker build checks | Automated tests are not real-world court-data validation |

## Design decision
Prefer existing maintained libraries and provider-owned official human-access channels
over copying a scraping bypass. Use only public documentation and permitted
exports. Live KAD bulk/API access, rate limits and legal authorization are
**unconfirmed** as of this document; a source verification gate is necessary
before introducing an adapter.

The connected Inspector Resources MCP `get_resource(kad)` returns
`registry_checked=false`, `availability=not_checked_at_runtime` and
`access=public_website`. It is a useful catalogue card, not a court search API.

## Additional dependencies
No new paid connectors, trial accounts or external API credits are required for
the offline workbench. GitHub was already connected for code and CI; Inspector
Resources was already connected for its catalogue card. No service integrations
were silently created or charged.

## Next architecture gates
1. Replace SQLite single-user storage with controlled Postgres / encrypted
   object store and role-aware data policies.
2. Introduce user identity, audit log, retention, session expiry, and HTTPS/OAuth
   before allowing remote connections.
3. Benchmark PDF/OCR against licensed sample documents with expert review.
4. Approve provider-specific data access before any automatic source adapter.
5. Build a real source validation interface only with verified human authority.
