# DocShield Production Deployment & Cloudflare Migration Guide

> **Status**: **CLOUDFLARE HYBRID PRODUCTION ARCHITECTURE READY**  
> **Mandatory Regulatory Disclosures**:
> - *"DocShield is an independent AI-assisted document screening prototype and is not an official government verification service."*
> - *"Registry checks are simulated demonstration data."*

---

## 1. Architecture Overview (Phase 2 Decision)

DocShield uses a **split edge-frontend + container-backend architecture** that leverages Cloudflare's global edge network for the React SPA and security perimeter while keeping CPU/memory-intensive Python computer vision and biometric models on a container-capable Python runtime.

```
+---------------------------------------------------------------------------------+
|                                 Public Internet                                 |
|                            (Border Officer Browser)                             |
+---------------------------------------------------------------------------------+
                                        |
                                        v  HTTPS (TLS 1.3 / Cloudflare Edge)
+---------------------------------------------------------------------------------+
| 1. CLOUDFLARE PAGES (Frontend & Edge Security)                                  |
|    - Hosts compiled React 19 + Vite 7 static bundle (frontend/dist)             |
|    - Enforces CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff       |
|    - Serves SPA routes via _redirects (/* -> /index.html 200)                   |
|    - Optional Edge Reverse Proxy via Pages Function (functions/api/[[path]].js) |
+---------------------------------------------------------------------------------+
                                        |
                                        v  HTTPS API Calls (VITE_API_BASE_URL)
+---------------------------------------------------------------------------------+
| 2. PYTHON-CAPABLE CONTAINER BACKEND (FastAPI / Uvicorn / Docker)                |
|    - Active Primary: Railway (https://docshield-production.up.railway.app)      |
|    - Free-Tier Alternative: Hugging Face Spaces Docker (2 vCPU, 16 GB RAM)      |
|    - Strict CORS (No wildcard '*' in production; restricted to Pages origin)    |
|    - Cloudflare CF-Connecting-IP aware sliding-window rate limiting             |
|    - Offloaded threadpool execution for CPU-bound OCR, ELA, and dlib inference  |
+---------------------------------------------------------------------------------+
                                        |
              +-------------------------+-------------------------+
              v                         v                         v
+--------------------------+ +-----------------------+ +--------------------------+
| 3. AI / CV / ML PIPELINE | | 4. EPHEMERAL MEMORY   | | 5. PERSISTENCE & STORAGE |
| - Tesseract / EasyOCR    | | - In-memory Pillow /  | | - SQLite WAL (cases)     |
| - OpenCV Caffe SSD Face  | |   NumPy buffers       | | - mock_database.json     |
| - dlib 128-d ResNet      | | - Zero disk retention | | - Optional R2 / D1       |
| - JPEG ELA Forensics     | |   for raw uploads     | |   migration path         |
+--------------------------+ +-----------------------+ +--------------------------+
```

### Why Python CV/ML Remains on a Container Runtime (Not Cloudflare Workers)
Cloudflare Workers (including Python Workers via Pyodide/WASM) impose a **128 MB memory limit** and do not support native compiled C++/Fortran shared libraries or system binaries required by DocShield:
- `dlib` / `face_recognition` (compiled C++ 128-D ResNet face encoding model)
- `opencv-python-headless` (C++ OpenCV DNN Caffe SSD `res10_300x300_ssd_iter_140000_fp16.caffemodel`)
- `tesseract-ocr` (native C++ optical character recognition binary) & `easyocr` / `torch` (PyTorch CPU tensors requiring ~1.26 GB Peak RSS)

---

## 2. Local Development Setup

### 2.1 Backend (FastAPI + Python 3.11)
```bash
# 1. From repository root, install dependencies using Python 3.11
py -3.11 -m pip install -r backend/requirements.txt

# 2. Create local .env from template (optional)
cp .env.example .env

# 3. Start Uvicorn development server
py -3.11 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2.2 Frontend (React 19 + Vite 7)
```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install exact dependencies from package-lock.json
npm ci

# 3. Start Vite dev server (proxies /api, /health, /ready to http://127.0.0.1:8000)
npm run dev
```

---

## 3. Cloudflare Workers Deployment (`docshield.sivasankar-t1606.workers.dev`)

### 3.1 Build & Static Assets Pipeline
- **Frontend Source Directory**: `frontend/`
- **Production Build Command**: `npm run build` (runs `npm --prefix frontend ci && npm --prefix frontend run build` from `/` or `vite build` from `frontend/`)
- **Compiled Output Directory**: `frontend/dist` (`./dist` relative to `frontend/`)
- **Worker Entrypoint**: [`worker.js`](../worker.js) (and [`frontend/worker.js`](../frontend/worker.js))
- **Wrangler Configuration**: [`wrangler.toml`](../wrangler.toml) (and [`frontend/wrangler.toml`](../frontend/wrangler.toml))
  - `[assets]` binds `./frontend/dist` (or `./dist`) to `env.ASSETS`.
  - Serves `/assets/*.js` with `application/javascript; charset=utf-8` and `/assets/*.css` with `text/css; charset=utf-8`.
  - Blocks `/src/*` and returns `404 Not Found` (`text/plain`) for any missing `.js`/`.css`/image file so the browser never receives `text/html` for module scripts.
  - Serves compiled `/index.html` (`200 OK`) for extensionless SPA client routes (`/`, `/screening`, `/history`, `/methodology`, `/privacy`).
  - Proxies `/api/*`, `/health`, and `/ready` to `BACKEND_ORIGIN` (`https://docshield-production.up.railway.app`).

### 3.2 Step-by-Step Cloudflare Workers Builds Setup
1. Open the [Cloudflare Dashboard](https://dash.cloudflare.com/) → **Compute (Workers & Pages)** → **`docshield`** → **Settings** → **Build**.
2. Configure the **Build settings**:
   | Setting | Recommended Value (Root = `/`) | Alternative Value (Root = `frontend`) |
   |---|---|---|
   | **Production branch** | `cloudflare-migration` | `cloudflare-migration` |
   | **Root directory** | `/` | `frontend` |
   | **Build command** | `npm run build` | `npm ci && npm run build` |
   | **Deploy command** | `npx wrangler deploy` | `npx wrangler deploy` |
3. *(Optional)* Under **Build variables**, set:
   - `VITE_API_BASE_URL` = `https://docshield-production.up.railway.app` *(already defaulted in `frontend/.env.production`)*
   - `VITE_APP_MODE` = `PROTOTYPE`
4. Save and trigger **Retry build / Deploy** on the latest commit of `cloudflare-migration`.

---

## 4. Backend Hosting & Free-Tier Investigation (Phase 6)

### 4.1 Empirical Resource & Latency Profile
Measured on the real DocShield AI pipeline (`backend/tests/performance_report.json` & `backend/tests/evaluation_report.json`):
- **Cold Module & Model Initialization**: `7.24 seconds`
- **Base Memory Footprint (RSS after startup)**: `490.0 MB`
- **Peak Memory Footprint (RSS during OCR + Caffe SSD + dlib + ELA)**: **`1,263.0 MB` (~1.26 GB)**
- **Warm Request Duration (`/api/analyze-document`)**:
  - Live Railway Container (Tesseract + Caffe SSD + dlib + ELA): **`1,114 ms` (~1.11 seconds)**
  - Local CPU with EasyOCR fallback: **`1,820 ms – 2,550 ms` (~1.8–2.5 seconds)**

### 4.2 Evaluation of Python-Capable Hosting Options

| Platform | Tier | RAM / CPU | Timeout | Suitability Verdict |
|---|---|---|---|---|
| **Railway** (`docshield-production.up.railway.app`) | Active Prototype / Hobby | Up to 8 GB RAM / 8 vCPU | 100s+ | **PASS (Recommended Primary)** — Already live, handles 1.26 GB peak RSS effortlessly, ~1.1s warm latency. |
| **Hugging Face Spaces** (Docker SDK) | **Free Tier ($0/mo)** | **16 GB RAM / 2 vCPU** | 60s+ | **PASS (Best True Free-Tier Option)** — 16 GB RAM easily accommodates PyTorch + EasyOCR + OpenCV + dlib without OOM crashes. |
| **Render** | Free Web Service | 512 MB RAM / 0.1 CPU | 100s | **FAIL (Unsuitable)** — 512 MB RAM Limit causes immediate Out-Of-Memory (OOM) crash when loading PyTorch/EasyOCR/dlib (~1.26 GB RSS). |
| **Fly.io** | Legacy Free / Pay-as-you-go | 256 MB – 512 MB default | 60s | **FAIL on 256/512 MB** — Requires paid 2 GB+ VM scaling. |
| **Cloudflare Workers** | Free / Paid | 128 MB WASM | 30s CPU | **FAIL (Incompatible)** — Cannot execute native C++ `dlib`, `OpenCV DNN`, `Tesseract`, or 1.26 GB PyTorch models. |

### 4.3 Standalone Backend Deployment (`backend/Dockerfile`)
To deploy the FastAPI backend independently of the frontend (e.g., on Railway, Hugging Face Spaces, Cloud Run, or any Docker host):
```bash
# Build standalone backend container from repository root
docker build -f backend/Dockerfile -t docshield-backend:latest .

# Run standalone backend container
docker run -p 8000:8000 \
  -e DOCSHIELD_ENV=production \
  -e DOCSHIELD_MODE=PROTOTYPE \
  -e FRONTEND_ORIGIN=https://docshield.pages.dev \
  -e DOCSHIELD_OFFICER_KEY=replace-with-strong-32-char-secret \
  docshield-backend:latest
```

---

## 5. Storage Architecture Evaluation (Phase 7)

| Storage Component | Current Implementation | Production Behavior & Cloudflare R2 / D1 Evaluation |
|---|---|---|
| **Uploaded Document & Face Images** | **Ephemeral In-Memory (`io.BytesIO`)** | Controlled by `ENABLE_SOURCE_IMAGE_STORAGE=false`. Raw biometric uploads are **never** written to disk, satisfying privacy-by-design. Small base64 thumbnails are stored inside the case record. **Cloudflare R2** is only needed if long-term archival of raw high-res evidence files is desired in a future phase. |
| **Case Audit History & Sessions** | **SQLite WAL (`backend/data/docshield.db`)** | Uses SQLAlchemy with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`, plus automatic 24-hour retention pruning (`DATA_RETENTION_HOURS=24`). Fully functional for public prototype use. Can be pointed to external PostgreSQL via `DATABASE_URL` or bridged to **Cloudflare D1** HTTP API if multi-region stateless replicas are introduced later. |
| **Watchlist Registry** | **Read-Only JSON (`backend/data/mock_database.json`)** | Bundled with the backend container; loaded into memory at startup with graceful `UNAVAILABLE` degradation if missing. |
| **Pre-trained CV/ML Weights** | **Container Layer (`backend/models_weights/`)** | Bundled directly in the Docker image (`deploy.prototxt` & `res10_300x300_ssd_iter_140000_fp16.caffemodel`) so cold starts never depend on external weight downloads. |

---

## 6. Environment Variables Reference (Phase 4, 8 & 13)

### 6.1 PUBLIC Variables (Frontend — Cloudflare Pages)
> **IMPORTANT**: Variables prefixed with `VITE_` are statically compiled into the public frontend JavaScript bundle. Never place secrets here.

| Variable | Value (Development) | Value (Production) | Purpose |
|---|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | `https://docshield-production.up.railway.app` | Target FastAPI backend origin |
| `VITE_APP_MODE` | `PROTOTYPE` | `PROTOTYPE` | Controls UI prototype disclaimer badges |

### 6.2 PRIVATE Variables (Backend — Railway / Docker Runtime)
> **SECURITY**: Configure these only in the backend container environment. Never commit `.env` files.

| Variable | Default / Example | Purpose |
|---|---|---|
| `DOCSHIELD_ENV` | `production` | Disables `/api/docs`, `/api/redoc`, and `/api/debug`; enables strict error sanitization |
| `DOCSHIELD_MODE` | `PROTOTYPE` | Enforces prototype disclosures (`DEMO`, `PROTOTYPE`, `OPERATIONAL`) |
| `DOCSHIELD_OFFICER_KEY` | *(Set a strong 32+ char secret)* | Required in `X-Officer-Key` header for `/api/cases` and `/api/case/{id}/review` |
| `FRONTEND_ORIGIN` | `https://docshield.pages.dev` | Primary Cloudflare Pages frontend origin permitted by CORS |
| `CORS_ORIGINS` | `https://docshield.pages.dev` | Comma-separated list of allowed origins (wildcard `*` is stripped in production) |
| `CORS_ORIGIN_REGEX` | `^https://([a-z0-9-]+\.)?docshield(-[a-z0-9-]+)?\.pages\.dev$` | Permits Cloudflare Pages branch preview deployments (`https://<hash>.docshield.pages.dev`) |
| `DATABASE_URL` | `sqlite:///./backend/data/docshield.db` | SQLAlchemy database URL |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` (10 MB) | Enforces 10 MB upload cap |
| `MAX_IMAGE_PIXELS` | `10000000` (10 MP) | Prevents image decompression bomb attacks |
| `MAX_CONCURRENT_ANALYSIS` | `2` | Bounded semaphore preventing memory exhaustion under concurrent load |
| `RATE_LIMIT_ANALYZE_PER_MINUTE` | `10` | Per-IP rate limit on `/api/analyze-document` using `CF-Connecting-IP` |
| `ENABLE_SOURCE_IMAGE_STORAGE` | `false` | Purges raw biometric images immediately after in-memory processing |

---

## 7. Railway Coexistence & Retirement Checklist (Phase 14)

The existing Railway deployment (`https://docshield-production.up.railway.app`) **must remain operational** as the active Python AI/CV backend (and fallback unified host) until all items below are verified in production:

- [x] `cloudflare-migration` branch created without modifying `master`.
- [x] Frontend build (`npm ci && npm run build`) succeeds cleanly into `frontend/dist` with `_headers` and `_redirects`.
- [x] Frontend `VITE_API_BASE_URL` configurable architecture verified with 45s timeout and sanitized error handling.
- [x] Backend CORS hardened (no wildcard `*` in production; supports `FRONTEND_ORIGIN` and `*.docshield.pages.dev`).
- [x] Backend rate limiter extracts real client IP from Cloudflare `CF-Connecting-IP`.
- [x] All 77 automated pytest tests and empirical sample evaluations pass.
- [ ] Connect `SivaSankarThirumalasetty/DocShield` (`cloudflare-migration` branch) in the Cloudflare Pages dashboard and verify the live `*.pages.dev` URL end-to-end before retiring any legacy configuration.
