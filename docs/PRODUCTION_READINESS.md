# Production Readiness

**Status: NOT READY FOR COMMERCIAL RELEASE.** Suitable at most as a supervised public
demonstration of an advisory prototype using synthetic samples.

## Release blockers (commercial / operational use)

| # | Blocker | Owner action |
|---|---|---|
| B1 | No model validation on representative, consented data; heuristic, uncalibrated score; no bias evaluation. | Commission a validation study (see PRODUCT_LIMITATIONS). |
| B2 | No legal / regulatory review (Aadhaar Act & regulations, DPDP Act 2023, sector rules). Processing Aadhaar images may itself be restricted. | Qualified legal review before any real-data use. |
| B3 | Model licences unverified for commercial redistribution: dlib 68-point landmark model (iBUG 300-W terms) shipped in `face_recognition_models`; OpenCV res10 SSD weights provenance. No project LICENSE. | Legal/licence review; replace models if needed; choose a licence. |
| B4 | Reviewer identity is bearer-token only: no SSO, MFA, admin UI, or self-service revocation. | Integrate an identity provider (e.g. Cloudflare Access) for reviewers. |
| B5 | Single container instance; rate limiting is approximate per location. A distributed flood degrades availability and raises cost. | Add Cloudflare WAF / rate-limiting rules on the zone, a budget alert, and capacity testing. |
| B6 | Live deployment of this commit not yet performed/verified (see final report). | Configure CI secrets and approve the production environment. |

## Accepted risks (documented)

* `setuptools==80.10.2` has two advisories (PYSEC-2026-3447, GHSA-xmj3-9gf7-h52w) affecting
  packaging on Windows/macOS, not runtime on Linux. Pinned because `face_recognition_models`
  needs `pkg_resources`. Ignored explicitly in CI.
* Python dependencies are version-pinned but not hash-pinned; EasyOCR weights are fetched at
  image build time without checksum verification.
* `wrangler deploy` is not transactional: new Worker code can briefly talk to the old container.

## Operational readiness

| Area | State |
|---|---|
| Health / readiness | `/api/health` (computed), `/api/ready` (Worker + D1 + container models, reports commit) |
| Deploy gating | CI must pass; readiness must report the new commit; live smoke tests must pass |
| Rollback | `docs/ROLLBACK.md` |
| Observability | Workers Logs enabled; JSON structured edge logs with request ids; backend access logs with request ids. No alerting configured. |
| Backups | D1 Time Travel (platform feature); retention 24 h for cases by design |
| Cost controls | `sleepAfter = 15m`, frontend stops polling once ready, `max_instances = 2` |

## Owner-side cleanup (not done automatically)

* The previous setup registered a Windows startup task / watchdog on the owner's PC that
  runs the old backend behind a Cloudflare Quick Tunnel. Stop it once the Cloudflare
  deployment is verified — the old backend has no authentication on officer routes.
* Delete obsolete Worker secrets `BACKEND_ORIGIN` and `DOCSHIELD_OFFICER_KEY` if they exist.
* The Railway service is left intact for recovery, pending owner approval to retire it.

## Cost and resources (Workers Paid, prices as published 2026-10)

`standard-2` = 1 vCPU, 6 GiB memory, 12 GB disk. Memory and disk are billed on provisioned
size while the instance is awake; CPU on active use.

| Item | Rate | Per awake hour |
|---|---|---|
| Memory | $0.0000025 / GiB-s (25 GiB-h/month included) | 6 × 3600 × 0.0000025 = **$0.054** |
| Disk | $0.00000007 / GB-s (200 GB-h/month included) | 12 × 3600 × 0.00000007 = **$0.003** |
| CPU | $0.000020 / vCPU-s active (375 vCPU-min included) | ≤ $0.072 at 100 % busy |

* Included memory covers ≈ 4 awake-hours per month; included disk ≈ 16 hours.
* Each wake keeps the instance up ≥ 15 minutes (`sleepAfter`).
* Always-on worst case (730 h): ≈ $39 memory + $2 disk + CPU usage + $5 plan ≈ **$46+/month**.
* A light demo (e.g. 20 wakes/day × 15 min ≈ 150 h/month): ≈ $8 memory + small CPU/disk + $5.
* D1 and Workers requests at demo volumes fall within included usage.

Measured memory and latency figures come from the CI container job (see TEST_REPORT.md);
production cold-start time must be measured after the first live deploy.
