# Architecture

```
Browser ──HTTPS──▶ Cloudflare Worker "docshield"  (worker/src/index.js)
                     │  static assets (frontend/dist, Workers Static Assets)
                     │  /api/*  ──▶ auth, rate limits, size checks, D1 persistence
                     │
                     ├──▶ Cloudflare Container  DocShieldBackendContainer  (backend/Dockerfile)
                     │      FastAPI on :8000, stateless (PERSISTENCE_MODE=none), no internet egress
                     │      Tesseract + EasyOCR (PyTorch CPU) · OpenCV SSD face detector ·
                     │      dlib/face_recognition · ELA · Verhoeff/ICAO validators · risk fusion
                     │
                     └──▶ D1 "docshield-db"  (migrations/)
                            cases (redacted) · officers (token hashes) · audit_log
```

Nothing runs outside Cloudflare. There is no Railway, Render, tunnel or personal-PC dependency.

## Request routing (Worker, `worker/src/app.js`)

`run_worker_first: true` sends every request to the Worker first.

| Path | Handling |
|---|---|
| `GET /api/health`, `/health` | Proxied to container `/api/health` (computed module states). 503 JSON if the container does not respond. |
| `GET /api/ready`, `/ready` | Container `/ready` **and** a D1 `SELECT 1`. 200 only when both are ready. Includes deployed commit. |
| `POST /api/analyze-document` | Rate limit (per IP) → content-type & Content-Length checks (≤ 20 MB + framing) → container → on 200, redact and insert into D1, return result + one-time session token. |
| `POST /api/verify-face` | Rate limit + size checks → container. |
| `GET /api/case/:id` | D1 only. Submitter `X-Session-Token` (hash, constant-time) **or** reviewer bearer token in the same tenant. Otherwise 404. |
| `GET /api/cases` | Reviewer only, tenant-scoped, paginated. |
| `POST /api/case/:id/review` | Reviewer only; decision enum validated; identity from token; audit row. |
| `GET /api/officer/me` | Reviewer profile for the UI sign-in. |
| other `/api/*` | JSON 404. Never the SPA shell. |
| static | `ASSETS.fetch`; missing files with an extension → plain 404; extensionless navigations → `index.html`. HTML gets a strict CSP. |

Cron (`17 * * * *`) deletes expired cases and audit rows older than 90 days.

## Container lifecycle

* One named instance (`docshield-backend-v1`), `standard-2` (1 vCPU, 6 GiB, 12 GB disk), `sleepAfter = 15m`.
* `startAndWaitForPorts` waits up to 180 s: uvicorn binds only after the FastAPI lifespan has loaded EasyOCR (`PRELOAD_MODELS=true`).
* `/ready` inside the container requires Tesseract, EasyOCR, the face detector, dlib embeddings and the demo registry (`REQUIRE_FULL_PIPELINE=true`).
* Inside the container: `MAX_CONCURRENT_ANALYSIS=1`, requests wait ≤ 20 s for a slot, then 503 + `Retry-After`.

## Screening pipeline (`backend/api/routes.py`)

Each stage reports `COMPLETED | FAILED | UNAVAILABLE | NOT_APPLICABLE` in `pipeline[]`.

| # | Stage | Implementation | Failure behaviour |
|---|---|---|---|
| 1 | Decode & validate | magic bytes, Pillow verify, ≤ 10 MB, ≤ 10 MP, OpenCV decode, resize ≤ 1600 px, deskew | 400 / 413 |
| 2 | OCR | Tesseract, EasyOCR fallback | `UNAVAILABLE` (no engine) or `FAILED` (no text) |
| 3 | Classification & parsing | anchor-text rules; MRZ TD3 parser | `UNKNOWN` type, never guessed |
| 4 | Format / checksum / dates | Verhoeff (Aadhaar), ICAO 7-3-1 (MRZ), PAN/passport syntax, expiry, DOB plausibility | missing number ⇒ `INDETERMINATE`, not FAIL |
| 5 | Registry | **SIMULATED** 7-record JSON (`backend/data/mock_database.json`) | `UNAVAILABLE` if not loaded |
| 6 | ELA | JPEG re-save difference, heuristic thresholds | `UNAVAILABLE` |
| 7 | Face | OpenCV SSD detect; dlib 128-d embedding distance ≤ 0.60 | `NOT_APPLICABLE` without a person photo; `NOT_AVAILABLE` without dlib |
| 8 | Fusion | additive penalties, 0–100, bands 30/65 | unavailable/inconclusive evidence blocks `NO_ADVERSE_INDICATORS` |

## Data model (D1)

See `migrations/0001_initial_schema.sql`. `cases.result_json` is produced by
`worker/src/redact.js` (mirrors `backend/core/redaction.py`): no images, no OCR
text, no name/DOB/address/MRZ, masked document number.

## Local development

`backend` runs with `PERSISTENCE_MODE=sqlite` (local redacted SQLite store and
optional `DOCSHIELD_OFFICER_KEY`), and Vite proxies `/api` to it. The Cloudflare
deployment never uses that path.
