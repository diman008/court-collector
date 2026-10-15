# Judicial Intelligence v2.4: local lexical search, case comparison, Docling pilot
Updated 2026-10-15.

## 1. Full-text search (enabled by default)
- No paid API or embedding/LLM required.
- SQLite FTS5 with unicode61 tokenization for Cyrillic and Latin. Not a Russian
  morphological analyzer: different inflected forms may not match. No embeddings.
- Migrates previously imported evidence and text documents on first SearchStore
  initialization. Idempotent. SQLite triggers index subsequent inserts/deletes.
- Returns literal excerpts, source ID, stored document SHA-256, page/logical
  segment and stated provenance; every result marked UNVERIFIED.
- Search query is reduced to a bounded AND of quoted words; operator syntax
  is not accepted from users.
- Endpoints: GET /v1/fulltext?q=...&case_number=...&court=...&limit=...
- CLI: judicial-intelligence fulltext "доказательства поставки" --court Москва
- MCP (private, read-only): search_imported_court_text.

## 2. Two-case comparison
- GET /v1/compare?left=А40-123/2025&right=А55-456/2025
- CLI: judicial-intelligence compare А40-123/2025 А55-456/2025
- MCP: compare_imported_cases.
- Compares literal NK article mentions and unverified user-entered court act
  stage/result fields. Each side retains case and evidence references.
- Does NOT infer legally contradictory judgments, case similarity, a violation,
  finality, or whether a cited article applies.
- Requires authorized human verification of the primary documents and actual
  procedural statuses before any professional legal assessment.

## 3. Docling structured-PDF pilot (NOT active by default)
- Requires separately installed optional dependencies. May download model
  weights during installation or initialization if they are not pre-cached.
- Must run as a local isolated job against authorized non-sensitive test samples.
- No direct web URLs accepted: only local bytes converted through DocumentStream.
- Explicit offline flag required: HF_HUB_OFFLINE=1.
- Installs are performed separately from the base application:
  python -m pip install -e '.[docling]'
- Pre-cache Docling models and validate the environment before running. Then:
  HF_HUB_OFFLINE=1 judicial-intelligence pilot-docling ./sample.pdf
- Output is an evaluation preview: SHA-256, known page indices, text lengths and
  up to 120 characters per segment. It does not update the evidence database.
- If document layout provenance is missing, output is a *logical* location,
  not a fabricated physical PDF page.
- Docling pipelines/model downloads and resource usage are not fully assessed
  here; benchmark on licensed synthetic/public examples before enabling a
  production import path.
- Compare Docling vs pypdf/pytesseract for native PDF, scans, tables,
  citations, page mapping and Russian texts. Maintain true/false positives.

## 4. Data ingestion/rights gate
- No automated KAD or commercial portal collection. Permission for bulk
  programmatic retrieval is not established.
- Source registry remains the starting point (docs/SOURCE-REGISTRY.md).
- Search results cover ONLY authorized locally imported texts; no implication
  of comprehensive Russian case-law coverage.
- Never upload tax-secret/confidential materials to GitHub, public model
  services or this non-production prototype.

## 5. Deployment gate
Current single-user SQLite/API key is an alpha prototype. Production still
needs strong per-user authorization, approved location, encryption, retention,
audit log, isolated OCR/Docling workers, and documented provider access rights.

References:
- SQLite FTS5: https://www.sqlite.org/fts5.html
- Docling official usage: https://docling-project.github.io/docling/
- Docling DocumentConverter API:
  https://docling-project.github.io/docling/reference/document_converter/
