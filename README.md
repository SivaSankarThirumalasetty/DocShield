---
title: DocShield
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# DocShield: AI-Based Fake Identity & Document Screening System
**Smart India Hackathon 2026** | **Problem Statement:** SIH26188  
**Organization:** Ministry of Home Affairs (MHA) | **Department:** Sashastra Seema Bal (SSB)

> **Prototype Disclosure**: *DocShield is an independent AI-assisted document screening prototype and is not an official government verification service. Registry checks are simulated demonstration data.*

DocShield is a hybrid cloud AI-powered identity and travel document screening system tailored for border security checkposts, immigration checkpoints, and law enforcement agencies.

---

## Hybrid Cloud Architecture (Cloudflare Edge + Python AI/CV Backend)

```
+-----------------------------------------------------------------------------------+
|                                     End User                                       |
|                             (Border Officer Browser)                              |
+-----------------------------------------------------------------------------------+
                                          |
                                          v  HTTPS (TLS 1.3 / HSTS / WAF)
+-----------------------------------------------------------------------------------+
|                         CLOUDFLARE EDGE (Cloudflare Pages)                        |
|  - React 19 + Vite 7 SPA Static Bundle (frontend/dist)                            |
|  - Edge Security Headers (_headers: CSP, X-Frame-Options, Referrer-Policy)        |
|  - SPA Client Routing (_redirects: /* -> /index.html 200)                         |
|  - Optional Edge API Proxy (frontend/functions/api/[[path]].js)                   |
+-----------------------------------------------------------------------------------+
                                          |
                                          v  HTTPS REST API (VITE_API_BASE_URL)
+-----------------------------------------------------------------------------------+
|                     PYTHON / FASTAPI AI BACKEND (Docker Runtime)                  |
|  - FastAPI + Uvicorn ASGI + Rate Limiting (CF-Connecting-IP aware)                |
|  - OCR Pipeline: Tesseract OCR + EasyOCR (PyTorch CPU) + Adaptive CLAHE/Otsu      |
|  - Document Parser: Aadhaar, PAN, ICAO Doc 9303 TD3 Passport MRZ, Voter ID        |
|  - Cryptographic Validation: Verhoeff 12-Digit Checksum & ICAO 7-3-1 Check Digits |
|  - Forensic Tampering: Error Level Analysis (ELA) JPEG Q=90 Recompression         |
|  - Biometrics: OpenCV DNN Caffe SSD (res10_300x300) + dlib 128-d ResNet           |
|  - Multi-Factor Risk Engine: Explainable 0-100 Fusion Score                       |
|  - Persistence: SQLite WAL (docshield.db) + Simulated SSB Watchlist               |
+-----------------------------------------------------------------------------------+
```

---

## Directory Structure

```
DocShield/
├── backend/
│   ├── Dockerfile                  # Standalone Backend Dockerfile (Python 3.11 + Tesseract + dlib)
│   ├── main.py                     # FastAPI application entrypoint, CORS, security middleware
│   ├── requirements.txt            # Pinned Python dependencies
│   ├── api/
│   │   └── routes.py               # REST endpoints (/api/analyze-document, /api/verify-face, etc.)
│   ├── core/
│   │   ├── config.py               # Environment settings & CORS origin configuration
│   │   ├── rate_limit.py           # Cloudflare CF-Connecting-IP aware sliding-window rate limiter
│   │   ├── security.py             # Magic-byte upload validation, filename sanitization, Aadhaar redaction
│   │   └── logging.py              # Structured JSON logging
│   ├── services/
│   │   ├── ocr_service.py          # Tesseract & EasyOCR extraction with bounding boxes
│   │   ├── document_parser.py      # Document classification, ICAO TD3 MRZ & Aadhaar parsing
│   │   ├── validation_service.py   # Verhoeff 12-digit algorithm, ICAO 7-3-1, syntax & date checks
│   │   ├── tampering_service.py    # In-memory Error Level Analysis (ELA) & heatmap
│   │   ├── face_service.py         # OpenCV DNN Caffe SSD face detector & dlib 128-d ResNet matching
│   │   ├── risk_engine.py          # Multi-signal weighted risk score & explainable forensic reasons
│   │   ├── mock_database.py        # Simulated SSB registry, stolen ID, and watchlist lookups
│   │   ├── storage_service.py      # SQLAlchemy SQLite WAL persistence & cryptographic session auth
│   │   └── report_service.py       # Case persistence & officer review delegation
│   ├── models/
│   │   ├── schemas.py              # Pydantic v2 data schemas
│   │   └── db_models.py            # SQLAlchemy ORM models
│   ├── data/
│   │   └── mock_database.json      # Simulated demonstration watchlist records
│   ├── models_weights/             # Pre-trained OpenCV Caffe SSD weights
│   │   ├── deploy.prototxt
│   │   └── res10_300x300_ssd_iter_140000_fp16.caffemodel
│   └── tests/                      # 77 automated security, CV/ML, API, and Cloudflare migration tests
│
├── frontend/                       # Cloudflare Pages React 19 + Vite 7 Officer Screening SPA
│   ├── public/
│   │   ├── _headers                # Cloudflare Pages security & cache headers
│   │   ├── _redirects              # Cloudflare Pages SPA fallback routing
│   │   └── samples/                # Sample identity documents for instant browser testing
│   ├── functions/
│   │   └── api/[[path]].js         # Optional Cloudflare Pages Function reverse proxy
│   ├── src/
│   │   ├── App.jsx                 # Application shell & navigation
│   │   ├── api.js                  # Configurable API client with timeout & sanitized error handling
│   │   └── components/             # HomePage, ScreeningPage, ResultsView, CaseHistoryPage, etc.
│   ├── .env.example                # Public frontend environment variable template
│   ├── package.json
│   └── vite.config.js              # Vite build & local dev proxy configuration
│
├── docs/
│   └── DEPLOYMENT.md               # Comprehensive Cloudflare Workers & Container Deployment Guide
├── sample_data/                    # Reference document & face fixtures
├── Dockerfile                      # Unified multi-stage Dockerfile (Cloudflare Container / Docker compatible)
├── worker.js                       # Cloudflare Worker & DocShieldBackendContainer entrypoint
├── wrangler.toml                   # Cloudflare Workers & Containers configuration
├── .env.example                    # Backend private environment variable template
└── README.md
```

---

## Local Development

### Prerequisites
- **Python 3.11** (`py -3.11` on Windows or `python3.11` on Linux/macOS)
- **Node.js 20+** and `npm`
- *(Optional)* Tesseract OCR system binary (automatically falls back to EasyOCR if Tesseract binary is not installed)

### 1. Start the FastAPI Backend
From the repository root (`DocShield/`):
```bash
# Install Python dependencies
py -3.11 -m pip install -r backend/requirements.txt

# Copy environment template (optional for local dev)
cp .env.example .env

# Run FastAPI server on http://127.0.0.1:8000
py -3.11 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
- **Liveness Probe**: `http://127.0.0.1:8000/health`
- **Readiness Probe**: `http://127.0.0.1:8000/ready`
- **Interactive API Docs** *(development only)*: `http://127.0.0.1:8000/api/docs`

### 2. Start the React/Vite Frontend
In a second terminal:
```bash
cd frontend

# Install exact dependencies
npm ci

# Start Vite development server on http://localhost:5173
npm run dev
```
- Local development automatically routes `/api/*`, `/health`, and `/ready` to `http://127.0.0.1:8000` (configurable via `VITE_API_BASE_URL` in `frontend/.env`).

---

## Cloudflare Workers Deployment (Frontend + Edge Proxy)

DocShield's React/Vite frontend is configured for Git-based deployment on **Cloudflare Workers with Static Assets** (`https://docshield.sivasankar-t1606.workers.dev/`):

1. Open the **Cloudflare Dashboard** → **Compute (Workers & Pages)** → **`docshield` Worker** → **Settings** → **Build**.
2. Verify the **Git repository** connection (`SivaSankarThirumalasetty/DocShield`) and set the build configuration:
   - **Production branch**: `cloudflare-migration`
   - **Root directory**: `/` *(or `frontend` — both contain a valid `wrangler.toml` and `worker.js`)*
   - **Build command**: `npm run build`
   - **Deploy command**: `npx wrangler deploy`
3. *(Optional)* Configure **Build variables**:
   - `VITE_API_BASE_URL` = `https://docshield.sivasankar-t1606.workers.dev` *(already configured as the default in `frontend/.env.production`)*
   - `VITE_APP_MODE` = `PROTOTYPE`
4. Save and trigger a deployment. Wrangler will compile the Vite React app into `frontend/dist` and upload only the compiled `dist` bundle (`index.html`, `/assets/index-<hash>.js`, `/assets/index-<hash>.css`, `/samples/*`) along with `worker.js`.

---

## Backend Deployment (FastAPI + OpenCV + OCR + dlib)

Because the backend executes native C++ and PyTorch computer vision models (`OpenCV DNN`, `dlib 128-d ResNet`, `Tesseract/EasyOCR`) with a measured **Peak RSS of ~1.26 GB**, it runs on a **Cloudflare Container (`DocShieldBackendContainer`, `standard-2`)** routed via `https://docshield.sivasankar-t1606.workers.dev/api/*`:

- **Option A — Cloudflare Containers (Primary Production Backend)**:
  - Routed via `https://docshield.sivasankar-t1606.workers.dev` (`DocShieldBackendContainer` Durable Object on port `8000`).
  - Uses `backend/Dockerfile` configured in `wrangler.toml`.
- **Option B — Standalone Docker Container (`backend/Dockerfile` or `Dockerfile`)**:
  - Can also be deployed on any Docker-compatible container runtime on port `8000`.

See **[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)** for full step-by-step instructions, resource benchmarks, storage architecture, and security configuration.

---

## Environment Variables (Public vs Private Separation)

### PUBLIC Frontend Variables (`frontend/.env` / Cloudflare Workers)
> **Warning**: All `VITE_*` variables are embedded into the public JavaScript bundle at build time. **Never** put private keys or officer tokens in `VITE_*` variables.

| Variable | Example / Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `https://docshield.sivasankar-t1606.workers.dev` | Base URL for the Cloudflare Worker/Container API (`http://127.0.0.1:8000` in local dev) |
| `VITE_APP_MODE` | `PROTOTYPE` | Displays prototype notices in the UI |

### PRIVATE Backend Variables (`.env` / Cloudflare Container / Docker Runtime)
> **Security**: Keep these strictly on the backend server. Never commit `.env` to Git.

| Variable | Example / Default | Description |
|---|---|---|
| `DOCSHIELD_ENV` | `production` | Disables `/api/docs`, `/api/redoc`, and `/api/debug` in production |
| `DOCSHIELD_MODE` | `PROTOTYPE` | Operational mode (`DEMO`, `PROTOTYPE`, `OPERATIONAL`) |
| `DOCSHIELD_OFFICER_KEY` | *(Secret 32+ char token)* | Required in `X-Officer-Key` header for `/api/cases` and officer overrides |
| `FRONTEND_ORIGIN` | `https://docshield.sivasankar-t1606.workers.dev` | Explicitly allowed Cloudflare Worker frontend origin for CORS |
| `CORS_ORIGINS` | `https://docshield.sivasankar-t1606.workers.dev` | Comma-separated list of allowed CORS origins (never `*` in production) |
| `CORS_ORIGIN_REGEX` | `^https://([a-zA-Z0-9-]+\.)*docshield(-[a-zA-Z0-9-]+)?\.(pages|workers)\.dev$` | Regex matching Cloudflare Workers & Pages subdomains |
| `DATABASE_URL` | `sqlite:///./backend/data/docshield.db` | SQLite WAL or PostgreSQL connection string |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | 10 MB maximum upload size |
| `MAX_IMAGE_PIXELS` | `10000000` | 10 MP limit against decompression bombs |
| `MAX_CONCURRENT_ANALYSIS` | `2` | Semaphore limiting concurrent heavy CV/ML pipelines |
| `RATE_LIMIT_ANALYZE_PER_MINUTE` | `10` | Per-IP rate limit (respects Cloudflare `CF-Connecting-IP`) |
| `ENABLE_SOURCE_IMAGE_STORAGE` | `false` | Keeps raw biometric uploads ephemeral in memory |

---

## Core API Endpoints

- `GET /health` — Liveness probe (`200 OK`)
- `GET /ready` — Readiness probe verifying SQLite DB, OCR engine, Caffe SSD face detector, and watchlist (`200 OK`)
- `GET /api/health` — Detailed module status for frontend status indicator
- `POST /api/analyze-document` — Full 7-stage document & biometric screening pipeline (`multipart/form-data`)
- `POST /api/verify-face` — Standalone 1:1 face verification (`multipart/form-data`)
- `GET /api/case/{case_id}` — Retrieves forensic dossier (requires `X-Session-Token` or `X-Officer-Key`)
- `GET /api/cases` — Lists screening history (requires `X-Officer-Key`)
- `POST /api/case/{case_id}/review` — Submits officer decision override (requires `X-Officer-Key`)

---

## Running Automated Tests

```bash
# Run all 77 unit, adversarial, security, and Cloudflare migration tests
py -3.11 -m pytest backend/tests -v

# Run empirical AI/CV pipeline benchmark on sample documents
py -3.11 backend/tests/evaluate_ai_pipeline.py
```
