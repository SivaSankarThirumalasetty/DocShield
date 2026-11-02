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

## Not yet verified

* Full pipeline in the production image (CI `container` job) — pending first CI run.
* Live deployment, cold-start latency, production memory, concurrent load — pending deploy.
* Accuracy of any kind — see PRODUCT_LIMITATIONS.md. Unit tests passing says nothing about accuracy.
