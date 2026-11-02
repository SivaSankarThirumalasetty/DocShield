# DocShield Audit — 2026-11-02

Baseline: branch `cloudflare-migration` at `e1fdbc4`, compared against `master` (`9eb0f3d`).
Every finding below was checked against the code or the live site; earlier audit
documents and test counts in the repository were not relied on.

## Baseline state

| Item | Observed |
|---|---|
| Live site `https://docshield.sivasankar-t1606.workers.dev/` | `/` returned 200 (frontend). **Every API path (`/api/health`, `/api/ready`, `/health`, `/ready`) returned 502** "Screening backend is temporarily unreachable". No working backend. |
| Deployed Worker | Contains a `DocShieldBackendContainer` class **and** a `BACKEND_ORIGIN` fallback to a Cloudflare Quick Tunnel pointing at the owner's Windows PC (`scripts/start-cloudflare-tunnel.ps1`, `keep-tunnel-alive.ps1`). |
| Baseline tests | 85 passed, 1 failed (`test_end_to_end_real_samples_and_verify_face`, needs real OCR). |
| Sample images | 4 synthetic cartoon images (no real people or real documents). Safe to keep. |
| Git history secret scan | No API tokens or private keys found. The hard-coded default officer key `docshield-officer-secret-key-change-in-production` is public in history and must be treated as compromised. |
| Tooling on audit machine | Python 3.11, Node 24, Git. **No Docker, no `gh`, Wrangler not authenticated.** Cloudflare connector (MCP) authenticated to the account. |

## Findings

### Critical

| ID | Finding | Status |
|---|---|---|
| C1 | **Authentication bypass.** The Worker injected `X-Officer-Key` (env value or the public default) into *every* proxied request, so any anonymous visitor had officer access to all cases and reviews. | Fixed — Worker no longer forwards any officer key; reviewer auth is per-person bearer tokens validated in the Worker against D1. |
| C2 | Single shared, hard-coded officer key default in backend config. | Fixed — no default; local-only key; production uses per-reviewer hashed tokens with expiry/revocation. |
| C3 | Production backend depended on a tunnel to a personal Windows PC (auto-start watchdog registered at login). Not Cloudflare-hosted; currently down. | Fixed in code — tunnel path and scripts removed; Worker routes only to the Cloudflare Container. The owner's local startup entry is **not** removed by this change (see PRODUCTION_READINESS). |
| C4 | Unavailable/failed signals could produce enforcement-style outcomes: OCR returning nothing produced an Aadhaar "12 digits required (found 0)" **critical** failure → HIGH "DETENTION_ALERT". | Fixed — missing extraction is INDETERMINATE; regression tests added. |

### High

| ID | Finding | Status |
|---|---|---|
| H1 | Verdicts and UI text used enforcement language ("Standard border clearance granted", "detain", "CLEARED FOR ENTRY", "DENIED ENTRY", "DETAINED"). | Fixed — advisory verdicts only; reviewer decisions are assessment records. |
| H2 | `/api/health` hard-coded every module to `true`; frontend showed "Engine Ready" from liveness alone. | Fixed — computed module states; UI derives status from `/api/ready` (Worker + D1 + container models). |
| H3 | Persistence was SQLite inside an ephemeral container; stored full extracted fields (name, DOB, address, OCR text). | Fixed — container is stateless; Worker stores redacted records in D1 with 24 h retention and hourly purge. |
| H4 | Unknown-document / no-checksum cases scored as validation PASS (no critical failure ⇒ "valid"); a privacy-mask info flag also counted as a passed structural check. | Fixed — PASS requires a real format/checksum check to pass. |
| H5 | SPA catch-all in FastAPI returned `index.html` (200) for unknown `/api/*` paths when the dist folder was present. | Fixed — backend is JSON-only; Worker returns JSON 404 for unknown API paths and real 404s for missing assets. |
| H6 | Officer identity on reviews came from the request body (spoofable). | Fixed — identity comes from the authenticated token record. |
| H7 | EasyOCR weights were not in the image; first request would download from the internet. | Fixed — weights baked at build; runtime downloads disabled; container has no internet egress. |

### Medium

| ID | Finding | Status |
|---|---|---|
| M1 | Wildcard `Access-Control-Allow-Origin: *` on assets; credentialed CORS regex for `*.pages.dev`; CSP `connect-src *`. | Fixed — same-origin; strict CSP on HTML; JSON-only CSP on API. |
| M2 | Officer key stored in `localStorage`. | Fixed — reviewer token in `sessionStorage` only. |
| M3 | Case lookups distinguished 403 vs 404 (enumeration signal); non-constant-time token compare. | Fixed — uniform 404; constant-time compare. |
| M4 | Exception text and file paths returned in API responses (face/ELA notes) and logs could contain PII via tracebacks. | Fixed — generic messages; log formatter redacts whole records incl. tracebacks. |
| M5 | Unpinned dependencies (`>=`), unpinned torch; `setuptools` removal of `pkg_resources` would break `face_recognition_models`. | Fixed — exact pins; image build verifies the face detector loads. |
| M6 | Container ran as root with `chmod 777`; build tools in runtime image. | Fixed — multi-stage build, non-root user. |
| M7 | In-memory rate-limit table grew without bound. | Fixed — bounded; edge Rate Limiting binding is primary. |
| M8 | Unbounded queueing for the analysis semaphore. | Fixed — 20 s acquire timeout → 503 with `Retry-After`. |
| M9 | Interactive API docs enabled unless env name was exactly `production`. | Container always runs `DOCSHIELD_ENV=production`; docs/openapi disabled there. |

### Low / Informational

| ID | Finding | Status |
|---|---|---|
| L1 | Duplicated `worker.js` / `wrangler.toml` in root and `frontend/`; stale `render.yaml`; root `Dockerfile` serving SPA from Python. | Removed. |
| L2 | Methodology page presented N=3 synthetic smoke-test numbers as "accuracy". | Relabelled as non-accuracy smoke results. |
| L3 | Privacy copy claimed Aadhaar Act compliance. | Removed claim; masking described as a safeguard only. |
| I1 | `face_recognition_models` ships dlib's 68-point landmark model trained on iBUG 300-W, whose terms restrict commercial use. The code path uses the 5-point model, but the 68-point file is redistributed in the image. | **Open** — legal review needed before commercial use. |
| I2 | OpenCV res10 SSD Caffe face detector weights: provenance documented only as "from source pack"; licence not verified in-repo. | **Open** — verify licence. |
| I3 | No LICENSE file. Ownership/third-party obligations unverified. | **Open** — owner decision. |
