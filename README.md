# DocShield

AI-assisted identity-document **screening prototype**. It extracts text from a document
image, runs format/checksum checks (Aadhaar Verhoeff, passport MRZ), a heuristic
image-forensics check (ELA), optional face comparison against a person photo, and a
lookup against a **simulated** demo registry, then explains the combined advisory result.

> **Prototype / advisory only.** DocShield is not a government verification service. It
> performs no real registry, police or watchlist lookup. ELA is not proof of forgery, face
> similarity is not a probability of identity, and the score is an uncalibrated heuristic.
> A qualified human reviewer makes every decision. See
> [docs/PRODUCT_LIMITATIONS.md](docs/PRODUCT_LIMITATIONS.md).

Live: https://docshield.sivasankar-t1606.workers.dev (Cloudflare Workers + Containers + D1)

## Architecture

Browser → Cloudflare Worker (static React app + `/api/*`) → Cloudflare Container (FastAPI,
Tesseract, EasyOCR, OpenCV, dlib) and D1 (redacted case records, reviewer tokens, audit log).
Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
frontend/   React + Vite UI
worker/     Cloudflare Worker (routing, auth, rate limits, D1) + tests
backend/    FastAPI screening pipeline, Dockerfile, tests
migrations/ D1 schema
scripts/    create-officer-token.mjs (reviewer credentials)
sample_data synthetic test images only
```

## Local development

Prerequisites: Python 3.11, Node 22.5+, optionally Tesseract (without it OCR is reported
UNAVAILABLE, which is the intended degraded behaviour).

```bash
python -m venv .venv && .venv/Scripts/pip install -r backend/requirements-dev.txt
```

```bash
.venv/Scripts/python -m uvicorn backend.main:app --reload --port 8000
```

```bash
npm --prefix frontend ci && npm --prefix frontend run dev
```

Open http://localhost:5173 (Vite proxies `/api` to :8000). The full ML stack
(`backend/requirements.txt`, incl. dlib and PyTorch) is easiest to run via Docker:

```bash
docker build -t docshield-backend backend/ && docker run -p 8000:8000 -e PERSISTENCE_MODE=sqlite docshield-backend
```

Environment variables: [.env.example](.env.example). Never put secrets in `VITE_*` variables.

## Tests

```bash
.venv/Scripts/python -m pytest backend/tests -q -rs
```

```bash
npm ci && npm run test:worker && npm --prefix frontend run lint
```

CI runs these plus an API contract test, the Docker image build, full-pipeline tests inside
the image, dependency audits and a secret scan: [.github/workflows/ci.yml](.github/workflows/ci.yml).
Latest local results: [docs/TEST_REPORT.md](docs/TEST_REPORT.md).

## API

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/health` | none | Module states (computed) |
| GET | `/api/ready` | none | 200 only when Worker, D1 and all models are ready |
| POST | `/api/analyze-document` | none, rate-limited | multipart `document`, optional `person_image`, `doc_type_hint` (`AADHAAR`/`PASSPORT`/`PAN`/`VOTER_ID`); ≤ 10 MB / 10 MP per image. Returns result, `pipeline[]`, `persistence`, one-time `session_token`. |
| GET | `/api/case/{id}` | `X-Session-Token` or reviewer bearer | Redacted record; 404 if not authorised |
| GET | `/api/cases` | reviewer bearer | Tenant-scoped list |
| POST | `/api/case/{id}/review` | reviewer bearer | `{decision, notes?, override_ai_verdict?}` |

Verdicts: `NO_ADVERSE_INDICATORS`, `INCOMPLETE_SCREENING`, `MANUAL_REVIEW_RECOMMENDED`,
`ESCALATE_FOR_EXPERT_REVIEW`. Reviewer decisions: `CONCUR_NO_FURTHER_ACTION`,
`REFER_FOR_PHYSICAL_INSPECTION`, `DOCUMENT_UNVERIFIABLE`, `ESCALATE_TO_SUPERVISOR`.

## Deployment, security, operations

* [Deployment](docs/DEPLOYMENT.md) · [Rollback](docs/ROLLBACK.md)
* [Security & privacy](docs/SECURITY_AND_PRIVACY.md) · [Threat model](docs/THREAT_MODEL.md)
* [Production readiness & costs](docs/PRODUCTION_READINESS.md) · [Audit](docs/AUDIT.md)

## Licence

No licence has been chosen yet; all rights reserved by the owner. Third-party model licences
(notably dlib landmark models and the OpenCV SSD face detector) have not been cleared for
commercial use — see [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md).
Attributions: [source_references/README.md](source_references/README.md).
