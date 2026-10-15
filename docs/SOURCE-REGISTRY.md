# SOURCE-REGISTRY: official evidence and permitted connectors
Updated: 2026-10-15. This inventory distinguishes availability of a human-facing website
from permission to use an automated API. No source has been approved for automated scraping.

| Source | Official address | Verified human-facing function | Automated data access | Next requirement |
|---|---|---|---|---|
| Arbitration Case Index / КАД | https://kad.arbitr.ru/ | Search by case number, participant, court and registration dates | NOT VERIFIED; internal 2025 endpoint not approved | Obtain documented interface/terms and permission, or rely on authorized exports |
| Electronic court-act signature checking | https://check.arbitr.ru/ | Verify a court-act electronic document and signatures in a human-guided workflow | NOT VERIFIED | Do not confuse SHA-256 with authenticating the court's signature |
| Official legal texts / Официальный интернет-портал правовой информации | https://pravo.gov.ru/ | Official publication and texts of legal acts, including amended versions | NOT VERIFIED | Ensure source and effective dates, amendment lineage |

## Implementation policy
1. Default adapter mode is manual local PDF, DOCX or TXT provided by an authorized person.
2. The label official_export does NOT verify source authenticity, case status or an electronic signature.
3. No bypass of HTTP 403/451, CAPTCHA, geo-controls, anti-bot measures, login or quotas.
4. A future connector must record source identity, entitlement, permitted operations, retention rules,
   rate limits, effective period, transport security, logging, test fixtures and review owner.
5. Do not run live requests against the provider until agreement or official documentation is checked.
6. Confidential data and tax secrecy must not be sent to external endpoints without an approved basis.
7. Public availability does not necessarily authorize unrestricted replication.

## Separation of provenance and conclusions
- Content integrity: original file SHA-256 and original bytes.
- Claimed provenance: source URL, user-provided source type, receipt timestamp.
- Verified provenance: not in alpha. Requires independent source or trusted signature verification.
- Extracted reference: literal quote, page or logical location, character offsets.
- Legal finding: expert judgment, procedural stage and applicable historical norm version.

## References
- KAD search: https://kad.arbitr.ru/
- Electronic signature verification: https://check.arbitr.ru/
- Government legal information: https://pravo.gov.ru/

Audit checkpoint: source connector approval pending. Only offline/manual import active.
