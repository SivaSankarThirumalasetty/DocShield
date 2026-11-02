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
| B5 | Single free backend instance (0.1 CPU, one screening at a time, sleeps when idle); Render states free instances are not for production. Rate limiting is approximate per location. | A paid, always-on backend for real use; WAF rules; capacity testing. |
| B6 | Live deployment not yet performed/verified. | Owner setup in DEPLOYMENT.md (Render account, Cloudflare token, GitHub secrets), then merge. |
| B7 | Uploaded identity images are processed by a third party (Render, Singapore). | Review Render terms/DPA and data-residency requirements before any real data. |
| B8 | Free image uses a third-party prebuilt dlib wheel (`dlib-bin`). | Verify provenance or build dlib from source in CI. |

## Accepted risks (documented)

* `setuptools==80.10.2` has two advisories (PYSEC-2026-3447, GHSA-xmj3-9gf7-h52w) affecting
  packaging on Windows/macOS, not runtime on Linux. Pinned because `face_recognition_models`
  needs `pkg_resources`. Ignored explicitly in CI.
* Python dependencies are version-pinned but not hash-pinned; EasyOCR weights are fetched at
  image build time without checksum verification.
* `wrangler deploy` is not transactional, and Render deploys the backend independently on push; for a short window the Worker and backend versions can differ. Both sides tolerate this (header record is optional; missing it means "not stored").

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

## Cost and resources (₹0 configuration)

| Component | Plan | Cost | Binding limits |
|---|---|---|---|
| Cloudflare Worker + static assets | Workers Free | ₹0 | 100k requests/day, 10 ms CPU/request |
| Cloudflare D1 `docshield-db` | Free | ₹0 | daily row read/write limits (queries fail, not billed) |
| Backend | Render Free web service | ₹0 | 512 MB, 0.1 CPU, sleeps after 15 min, 750 h/month |
| CI | GitHub Actions on a public repo | ₹0 | standard hosted-runner limits |

No payment method is required by this setup. Keep it that way: on Render, a payment method on file
enables overage billing; on Cloudflare, Containers/Workers Paid are not used.

Measured in CI (`free-image` job, commit a927482, container limited to 512 MB / 0.1 CPU):

| Metric | Value |
|---|---|
| Cold start to `/ready` 200 | 20 s (Render adds ~1 min wake when sleeping) |
| Screening latency (synthetic samples, with person photo) | 20.6 s, 20.7 s, 27.2 s |
| Peak memory | 258 MiB of 512 MiB, no OOM |
| Image size | 763 MB |

The paid alternative (`wrangler.containers.jsonc`, standard-2) would cost roughly $0.054/awake-hour
in memory beyond the included allowance plus the $5/month plan; it is not used.
