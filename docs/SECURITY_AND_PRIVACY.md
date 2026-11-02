# Security and Privacy

## Data handling

| Data | Where | Retention |
|---|---|---|
| Uploaded images | Worker memory → container memory during one request | Discarded after the response. Never written to disk or D1. |
| Full screening result (incl. previews, OCR text, extracted fields) | HTTP response to the submitter only (`Cache-Control: no-store`) | Not stored |
| Redacted case record | D1 `cases.result_json` | `CASE_RETENTION_HOURS` (24 h), hourly purge |
| Session token | Returned once; D1 stores SHA-256 only | With the case |
| Reviewer tokens | D1 stores SHA-256 only; browser keeps raw token in `sessionStorage` | Expiry set at creation (≤ 365 days), revocable |
| Audit log | D1 `audit_log` (actor, action, decision; no notes, no PII) | 90 days |
| Logs | Workers Logs / container stdout: request id, path, status, latency. PII-redacting formatter on backend logs. | Cloudflare plan retention |

Redacted records contain: document type, masked number (`XXXX-XXXX-1234` / `****1234`),
validation/ELA/face outcome flags, score, verdict, reasons, pipeline stages. They contain
no images, OCR text, names, dates of birth, addresses or MRZ lines.

Masking an Aadhaar number is a safeguard, **not** evidence of compliance with the Aadhaar
Act, the DPDP Act 2023 or any other law. That requires qualified legal review.

## Controls

* **Authentication**: per-reviewer 256-bit bearer tokens (hashed, expiring, revocable); failed
  attempts rate-limited. Submitters use a per-case capability token. No shared passwords.
* **Authorisation**: every case read/review checks token hash or reviewer tenant server-side.
  Unauthorised and non-existent cases both return 404. Reviewer identity on reviews comes from
  the token, not the request body.
* **Tenancy**: anonymous public submissions use tenant `public-demo`; reviewers see only their tenant.
* **CSRF**: no cookies are used; credentials are sent in headers, so cross-site requests cannot carry them.
* **Uploads**: content-type and Content-Length checked at the edge (≤ 20 MB per request);
  backend checks magic bytes, decodes, enforces 10 MB / 10 MP per image (decompression-bomb guard),
  sanitises filenames.
* **Abuse**: edge Rate Limiting binding (10 analyses/min/IP per location, approximate);
  backend semaphore with bounded queue wait; one container instance.
* **Headers**: HSTS, `nosniff`, `X-Frame-Options: DENY`, strict CSP (`script-src 'self'`,
  `connect-src 'self'`), JSON-only CSP on API responses, `no-store` on all API responses.
* **Errors**: only a short `detail` string leaves the system; tracebacks stay in server logs.
* **Container**: non-root, no internet egress (`enableInternet = false`), models baked in,
  no interactive docs or debug routes.
* **Supply chain**: exact dependency pins, lockfiles, pinned GitHub Action SHAs,
  `npm audit`, `pip-audit`, gitleaks on full history in CI.

## Credential rotation

The former default officer key (`docshield-officer-secret-key-change-in-production`) is in
public git history. It no longer grants anything in the new code. If any deployed
environment still sets `DOCSHIELD_OFFICER_KEY` or `BACKEND_ORIGIN` as Worker secrets,
delete them (`npx wrangler secret delete …`) after the new version is live.
If the old tunnel URL is still running on the owner's PC, stop it: it exposes the old,
unauthenticated backend directly.

## Known gaps

See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md).
