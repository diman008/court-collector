# Verification of judicial acts (manual trusted-source workflow)

The project currently checks **byte integrity only** using SHA-256. It does NOT
cryptographically validate a judge's electronic signature, registry entry, or the
legal finality of a judicial decision.

## Official verification
The Electronic Justice service at https://check.arbitr.ru/ states that users
should identify a case and an electronically signed judicial act, select the act,
upload the electronic document and its signature file(s), and run verification.

Capture in an approved internal record:
- Case number, court, decision date and document title as displayed at the source
- Time of verification, source URL, reported portal result (success/failure/unavailable)
- SHA-256 of the exact document submitted and SHA-256 of detached signature files
- Source reference, screenshot or permitted protocol as evidence (never fake a result)
- Reviewer ID and whether the original file equals the stored file's SHA-256

A portal result must be verified by a human. This alpha build does not change
verification_status in the database to "verified" automatically or through MCP.
Do NOT upload service/tax secret materials to a public website without lawful
authorization and approved policies.

## Authentication and access
A public court website does not imply automated bulk API access. Keep KAD
automated connector disabled until source-specific terms and access rights are
verified. Never bypass geoblocking, CAPTCHA, rate limits or service restrictions.

## OCR
For scanned PDF, use explicit local CLI option --ocr in an isolated environment.
Recognized text is unverified; character offsets refer to OCR output rather
than original pixels. Retain physical page numbers and inspect each quotation.
No cloud OCR, no background scheduling, no external document transmission.
