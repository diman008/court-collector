# Migration playbook (2025 legacy → Judicial Intelligence v2)

## Scope
- Sources: `diman008/kad` and `diman008/court-collector` (2025).
- Destination: `diman008/court-collector`, branch `reengineering/judicial-intelligence-v2`.
- Legacy snapshots are preserved as `legacy/kad_proxy_2025.py`,
  `legacy/court_collector_2025.py`, and `legacy/tax_rules_2025.yaml`.
- Original repositories and Git history are not deleted by this migration.

## Breaking changes
- Deprecated endpoints `/kad/search`, `/kad/details`, `/start`,
  `/status/{id}`, `/download/{id}` are **not** available in v2.
- `GET /v1/cases?q=...` searches only *locally registered* cases.
- `GET /v1/case?case_number=А40-123/2025` returns one case.
- `POST /v1/cases` creates a local case.
- `POST /v1/documents?case_number=...` uploads a text document.
- `GET /v1/documents?case_number=...` shows source metadata.
- `GET /v1/report?case_number=...` provides deterministic literal mentions.
- IDs with `/` belong in query parameters, **not in URL path segments**.
- API access requires `X-API-Key`; missing server key disables data APIs.

## Safe cutover checklist
1. Record default branch SHA and archive legacy sources; verify the original repos remain accessible.
2. Run `python -m pip install -e ".[test]"` and `python -m pytest -q`.
3. Verify Docker build and non-root execution; review dependencies and secrets.
4. Test import, duplicate import, missing case, invalid case and report on *synthetic* data.
5. Verify retention, location and authorization rules before using real-case documents.
6. Review dataset/export backup and recovery.
7. Approve changes via PR; only then merge into `main`.
8. Do not archive `kad` until all real-use scenarios are reproduced with permitted sources.
9. A live KAD integration is a separate deliverable; no 2025 fallback scraper is silently retained.

## Rollback
- `main` remains untouched until the PR is merged.
- After merge, revert the merge commit using standard GitHub controls if required.
- Never delete the 2025 legacy snapshots or repositories as part of rollback.
