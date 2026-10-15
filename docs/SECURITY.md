# Security and privacy boundary

**Current status:** development alpha, not internet-production or government-system approved.

1. No tax-secret, classified, sensitive or restricted case materials may be uploaded
   to a public repository or third-party service.
2. No court scraping, CAPTCHA bypass, rotating proxies or restrictions-avoidance
   features are enabled. Check site terms and permissions before any live connector.
3. The API is fail-closed without `JUDICIAL_API_KEY`. The header key is a basic
   MVP safeguard, **not** sufficient by itself for public production.
4. Expose the service only on loopback or a properly configured private gateway
   until TLS, per-user authorization, RBAC, rate limits, auditing and threat review exist.
5. SQLite is a local single-instance persistence method; use encryption at rest,
   controlled file permissions and encrypted backups for authorized deployments.
6. Raw documents and local databases must remain outside Git (see `.gitignore`).
   Avoid logging request bodies, API keys and judicial documents.
7. Source kind `official_export` is **user-provided metadata**, not independent
   verification. Every imported document is marked `unverified_user_input`.
8. SHA-256 verifies content integrity after capture; it does not authenticate the
   origin, authenticity or completeness of that text.
9. Extracted legal references are text matches only, not a claim of court finding,
   legal applicability or final judicial status.
10. Next controls: user roles, session expiry, audit events, retention/deletion,
    verified provenance, malware scanning, file-upload size limits, SSRF controls
    for future URL adapters, backup/restore exercises.

## v2.1 input and trust limitations
- Uploads are limited to 8 MiB and extracted documents to 200 PDF pages / 200000 characters.
- Only PDF and DOCX are accepted by the binary ingestion handler. Scanned PDFs do not undergo OCR.
- DOCX is a ZIP container. Extraction caps XML bytes and entry counts but requires continued hostile-file fuzzing.
- All original bytes are stored in SQLite; **filesystem permissions are not encryption**.
- Extraction is not verification of court origin or integrity of a signature.
- Source metadata, judicial events and legal versions are user-supplied and remain unverified.
- A private multiuser production deployment requires authorization, encryption, retention rules, structured audit logs and legal review.

## v2.2 alpha additions
- OCR is explicitly opt-in and local. Requires system Tesseract and installed
  Russian/English traineddata. Process hostile files only in isolated,
  resource-limited workers; Tesseract availability is not a security boundary.
- OCR page offsets index recognized text, not original PDF glyph geometry.
  Human checking of every citation remains mandatory.
- Private MCP exposes only READ operations; no external registry fetches or
  write tools. This is a local prototype, NOT a public ChatGPT plugin.
- X-API-Key and 127.0.0.1 binding are insufficient for internet deployment.
  Any public/private network rollout requires TLS, user-specific auth,
  authorization, audit, data retention policy and security review.
- Official signature validation is NOT implemented. See docs/VERIFICATION.md.
