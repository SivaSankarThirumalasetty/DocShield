# Test Report

Generated 2026-11-02 on the audit machine (Windows 11, Python 3.11, Node 24.21).
CI results are recorded in GitHub Actions for each commit; this file records only what
was actually run here. Nothing below was run in Docker or against the live site unless stated.

## Environment limits on the audit machine

No Docker, no Tesseract, no dlib/face_recognition, no EasyOCR/PyTorch. The full ML pipeline
therefore runs only in the CI `container` job (inside the production image). Locally, the
pipeline ran in degraded mode, which is itself a tested behaviour.

## Results

| Suite | Command | Result |
|---|---|---|
| Baseline before changes | `pytest backend/tests tests` | 85 passed, 1 failed (real-OCR e2e) |
| Backend unit / security / upload / auth / persistence / product-boundary | `pytest backend/tests -q -rs` | **95 passed, 1 skipped** (real-OCR e2e: needs Tesseract + dlib; runs in CI container job) |
| Worker unit (routing, auth, tenant isolation, D1 via real migration SQL, retention, redaction, limits) | `npm run test:worker` | **16 passed**, 1 skipped (contract suite, needs `BACKEND_URL`) |
| Worker ↔ FastAPI API contract (real uvicorn, `PERSISTENCE_MODE=none`) | `BACKEND_URL=http://127.0.0.1:8765 node --test worker/test/contract.test.mjs` | **4 passed** |
| Frontend lint | `npm --prefix frontend run lint` | clean (0 warnings) |
| Frontend build | `npm run build` | OK (JS 235.7 kB / 68.4 kB gzip) |
| Wrangler config + bundle | `wrangler deploy --dry-run --containers-rollout=none` | OK — all bindings resolve (DO, D1 `docshield-db`, 2 rate limiters, assets) |
| Wrangler with container build | `wrangler deploy --dry-run` | **Not run**: needs Docker |
| npm audit (prod deps, root + frontend) | `npm audit --omit=dev --audit-level=high` | 0 vulnerabilities |
| pip-audit runtime | `pip-audit -r backend/requirements.txt --no-deps` | 3 findings in setuptools (2 advisories), documented exceptions; 0 others |
| pip-audit dev | same for `requirements-dev.txt` | 0 |

### Degraded-mode evidence (local, no OCR engine)

Real request to a local backend (`PERSISTENCE_MODE=none`):

```
aadhaar_valid            MANUAL_REVIEW_RECOMMENDED MEDIUM 30 unavailable=['ocr'] validation=INDETERMINATE ocr_stage=UNAVAILABLE
aadhaar_invalid_checksum MANUAL_REVIEW_RECOMMENDED MEDIUM 30 unavailable=['ocr'] validation=INDETERMINATE ocr_stage=UNAVAILABLE
/ready -> 503 (ocr_tesseract=false, ocr_easyocr=false, face_embedding=false)
/api/docs -> 404 in production mode
```

Before the fix in this change, the same request produced `ESCALATE_FOR_EXPERT_REVIEW / HIGH / 65`
because an empty OCR result was scored as an Aadhaar checksum failure (finding C4).

## CI evidence (GitHub Actions, public annotations)

| Commit | Job | Result |
|---|---|---|
| 29fe048 | Full image (`backend/Dockerfile`, EasyOCR+PyTorch) | built; `/ready` 200; real screening of all 3 samples passed (OCR completed, invalid checksum detected) |
| a927482 | **Free image under 512 MB / 0.1 CPU** | `/ready` 200 after 20 s; direct call without edge secret → 401; screenings 20.6 / 20.7 / 27.2 s, all 8 stages COMPLETED, no unavailable signals, invalid checksum detected; peak 258 MiB; no OOM |
| a927482 | Frontend, Worker tests, wrangler dry-runs (free + containers config) | passed |
| a927482 | Backend tests (Linux + Tesseract), in-image tests | **failed**: `sanitize_filename` kept `....windowswin.ini` for Windows-style traversal on Linux. Fixed in 7707b97. |
| a927482 | gitleaks | **failed**: placeholder `DOCSHIELD_OFFICER_KEY=replace-with-…` in old commit 72f75745; reviewed, fingerprint-allowlisted in 7707b97 |

Note: the synthetic cartoon faces were reported as `MATCH`. That shows the pipeline runs; it says
nothing about face-comparison accuracy.

## Not yet verified

* Live deployment on Render + Cloudflare, real Render wake time, concurrent load — pending owner setup.
* Accuracy of any kind — see PRODUCT_LIMITATIONS.md. Unit tests passing says nothing about accuracy.
