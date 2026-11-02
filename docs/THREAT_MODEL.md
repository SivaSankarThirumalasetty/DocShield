# Threat Model

Assets: uploaded identity images and extracted fields (in flight), redacted case records,
reviewer tokens, the audit log, service availability, and the integrity of advisory outputs.

Trust boundaries: browser ↔ Worker (internet); Worker ↔ container (Cloudflare internal);
Worker ↔ D1; CI ↔ Cloudflare API (API token).

| # | Threat (STRIDE) | Vector | Mitigation | Residual risk |
|---|---|---|---|---|
| T1 | Spoofing a reviewer | Guess/steal token | 256-bit tokens, hashed at rest, expiry, revocation, failed-auth rate limit, `sessionStorage` only | XSS or a compromised device can steal a live token; no MFA / SSO |
| T2 | Broken object-level authorisation | Enumerate case IDs | Case ID + capability token or same-tenant reviewer; uniform 404 | None known |
| T3 | Cross-tenant access | Reviewer reads other tenant | Tenant check on every query | Tenant model is minimal (no admin UI) |
| T4 | Tampering with review identity | Body fields `officer_id` | Identity from token record | — |
| T5 | Repudiation | Reviewer denies a decision | Audit log with actor + timestamp | Audit rows are mutable by anyone with D1 access |
| T6 | Information disclosure — stored data | D1 leak | Redaction before storage, 24 h retention | Masked numbers + verdicts remain sensitive |
| T7 | Information disclosure — responses | CDN/browser caching | `no-store`, no cookies | Shared/public computers |
| T8 | Information disclosure — logs | PII in exceptions | Redacting formatter, generic errors | Workers platform logs request metadata |
| T9 | DoS — expensive inference | Flood `/api/analyze-document` | Edge rate limit, size limits, bounded queue, single instance | Rate limiting is per location and approximate; a distributed attacker can exhaust the single instance (availability only) and raise cost |
| T10 | DoS — decompression bombs | Huge-dimension images | 10 MP cap before full decode | — |
| T11 | Malicious file parsing | Crafted PNG/JPEG/WebP | Magic bytes + Pillow verify; container non-root, no egress | Parser CVEs in Pillow/OpenCV; keep pins updated |
| T12 | Model / supply-chain compromise | Malicious dependency or weights | Exact pins, lockfiles, pinned actions, weights baked at build | No hash-pinned pip install; weights downloaded at build time over HTTPS without checksum verification |
| T13 | CI credential theft | Workflow injection | Minimal-scope token in environment-gated job; PRs from forks get no secrets | Repository admins can read the deployment environment |
| T14 | Misuse of output | Treating advisory score as a decision | Advisory wording, visible notices, review console | Users can still over-trust the tool |
| T16 | Bypassing the edge | Calling the public Render URL directly to skip rate limits/auth | Backend rejects every request except `/health` without `X-DocShield-Edge-Auth` (constant-time); secret only in Worker secret + Render env | Secret rotation is manual; `/health` is public (no data) |
| T17 | Free-tier exhaustion | Traffic burns Render hours / D1 daily limits | Edge rate limits; 24 h retention; service suspends rather than bills (no payment method) | Site degrades to "engine unavailable" until reset |
| T15 | Adversarial documents | Crafted images to pass checks | Multiple independent signals, INDETERMINATE on missing evidence | Signals are heuristic; not robust to a determined forger |
