# DocShield Production Deployment Guide

> **Status**: **PUBLIC PROTOTYPE READY**  
> **Mandatory Regulatory Disclosures**:
> - *"DocShield is an independent AI-assisted document screening prototype and is not an official government verification service."*
> - *"Registry checks are simulated demonstration data."*

---

## 1. Executive Summary & Architecture

DocShield is packaged as a **single-container, unified web application** accessible via a single public URL. It eliminates the need to separately manage frontend development servers (Vite) and backend workers (Uvicorn).

```
+---------------------------------------------------------------------------------+
|                                 Public Internet                                 |
|                                       |                                         |
|                  https://docshield-production.up.railway.app                    |
+---------------------------------------------------------------------------------+
                                        |
                             [ Reverse Proxy / TLS ]
                                        |  (Port $PORT)
+---------------------------------------------------------------------------------+
| Single Docker Container                                                         |
|                                                                                 |
|   +-------------------------------------------------------------------------+   |
|   | Uvicorn Server (Python 3.11 / FastAPI ASGI)                             |   |
|   | Host: 0.0.0.0 | Port: ${PORT:-8000}                                      |   |
|   +-------------------------------------------------------------------------+   |
|          |                                                    |                 |
|          v                                                    v                 |
|   [ Static SPA Router ]                                [ API Subsystems ]       |
|   - /                                                  - /health (Liveness)     |
|   - /screening                                         - /ready (Readiness)     |
|   - /results                                           - /api/analyze-document  |
|   - /history                                           - /api/verify-face       |
|   - /methodology                                       - /api/cases (Auth)      |
|   - /privacy                                           - /api/officer/* (Auth)  |
|   - /assets/*                                                                   |
|   - /samples/*                                                                  |
|   (Precompiled React/Vite in frontend/dist)                                     |
+---------------------------------------------------------------------------------+
```

---

## 2. Target Deployment Platform: Railway

DocShield is primarily pre-configured for deployment on **Railway** (`docshield-production.up.railway.app`).

### 2.1 Configuration Files
- **[`railway.json`](file:///D:/DocShield/DocShield/railway.json)**:
  ```json
  {
    "$schema": "https://railway.app/railway.schema.json",
    "build": {
      "builder": "DOCKERFILE",
      "dockerfilePath": "Dockerfile"
    },
    "deploy": {
      "healthcheckPath": "/health",
      "healthcheckTimeout": 100,
      "restartPolicyType": "ON_FAILURE",
      "restartPolicyMaxRetries": 10
    }
  }
  ```
- **Port Handling**: Railway dynamically assigns a listening port at container startup via the `$PORT` environment variable. The DocShield entrypoint dynamically binds to `${PORT:-8000}`.

---

## 3. Multi-Stage Dockerfile Specification

The container build uses a two-stage process to minimize image size and eliminate build tools from the final runtime image:

### Stage 1: Frontend Build (`node:20-slim`)
- Installs npm packages (`npm ci`).
- Executes `npm run build` to create static HTML, CSS, and JS bundles in `frontend/dist`.
- Excludes development artifacts (`node_modules`) from the production image.

### Stage 2: Runtime Image (`python:3.11-slim`)
- Installs necessary system libraries:
  - `tesseract-ocr`, `tesseract-ocr-eng` (for OCR extraction)
  - `libgl1`, `libglib2.0-0`, `libsm6`, `libxext6` (for OpenCV computer vision operations)
  - `curl` (for healthcheck probing)
- Installs lightweight CPU-only PyTorch wheel (`torch`, `torchvision` via `https://download.pytorch.org/whl/cpu`).
- Installs Python dependencies (`backend/requirements.txt`).
- Copies backend source code, pre-trained Caffe models (`models_weights/`), and demonstration database (`data/`).
- Copies compiled frontend bundle from Stage 1 into `frontend/dist`.
- Configures healthcheck against `/health`.
- Launches Uvicorn dynamically binding to `${PORT:-8000}`.

---

## 4. Environment Variables Reference

Configure these in the Railway dashboard or `.env`:

| Variable | Default Value | Purpose |
|---|---|---|
| `DOCSHIELD_ENV` | `production` | Set to `production` to disable interactive Swagger `/api/docs` and enforce strict logging. |
| `DOCSHIELD_MODE` | `PROTOTYPE` | Enforces prototype disclaimer banners and demo database markers (`DEMO`, `PROTOTYPE`, `OPERATIONAL`). |
| `PORT` | `8000` | Injected by hosting provider (Railway/Render); server binds to this port. |
| `HOST` | `0.0.0.0` | Container network interface binding. |
| `CORS_ORIGINS` | `*` or comma-separated URLs | Allowed origins for API requests. Do not use wildcard `*` with credentials enabled. |
| `DOCSHIELD_OFFICER_KEY` | *(Set a secure secret)* | Secret token required for officer override and case history APIs via `X-Officer-Token` header. |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` (10 MB) | Rejects files exceeding 10 MB to prevent resource exhaustion. |
| `MAX_IMAGE_PIXELS` | `10000000` (10 MP) | Protects against decompression bomb exploits. |
| `MAX_CONCURRENT_ANALYSIS`| `2` | Limits concurrent active CV/ML pipelines to prevent memory exhaustion on small instances. |
| `RATE_LIMIT_ANALYZE_PER_MINUTE` | `10` | Restricts per-IP screening throughput to thwart DoS. |
| `ENABLE_SOURCE_IMAGE_STORAGE` | `false` | Privacy safeguard: when `false`, raw uploaded biometric images are purged from disk immediately. |
| `DATABASE_URL` | `sqlite:///./data/docshield.db` | Case metadata audit storage. Can be pointed to a persistent volume or PostgreSQL. |
| `DATA_RETENTION_HOURS` | `24` | Automated retention window for case audit metadata. |

---

## 5. Resource Sizing & Free-Tier Limitations

### Empirical Performance Profile
- **Cold Boot Time**: 6.92 seconds (model loading and database verification).
- **Warm Inference Latency**: ~1.8 seconds (OCR + Caffe Face Detection + MRZ Validation + Forensics + Risk Fusion).
- **Peak RSS (Memory Footprint)**: **1,261.6 MB** (~1.26 GB).

### Hosting Recommendations
> [!WARNING]
> **512 MB Free-Tier Containers Will OOM**: Standard entry-level free tiers (such as 512 MB RAM on free Render/Railway instances) **cannot** support PyTorch + OpenCV + EasyOCR in-memory simultaneously. Deploying to a 512 MB instance will trigger an Out-Of-Memory (OOM) crash during container initialization.

- **Minimum Required RAM**: **2.2 GB**
- **Recommended RAM**: **4.0 GB** (enables 2 concurrent screenings without throttling)
- **Minimum vCPU**: **2 vCPUs**
- **Hosting Tier**: Railway Hobby / Pro plan (with up to 8 GB RAM allocation).

---

## 6. Health & Readiness Probes

DocShield implements dual probe endpoints conforming to cloud deployment standards:

### 1. Liveness Probe: `GET /health`
- **Purpose**: Confirms the web process is running and responding to HTTP requests.
- **Response**: `HTTP 200 OK`
  ```json
  {
    "status": "healthy",
    "service": "DocShield Border Screening Engine",
    "version": "2.0.0",
    "timestamp": "2026-10-01T17:11:37.703627"
  }
  ```

### 2. Readiness Probe: `GET /ready`
- **Purpose**: Verifies that database connectivity, OCR engines, face detection models, and reference watchlists are active.
- **Response**: `HTTP 200 OK` (or `HTTP 503` if a dependency is unavailable)
  ```json
  {
    "status": "ready",
    "mode": "PROTOTYPE",
    "checks": {
      "database": true,
      "ocr_engine": true,
      "face_detector": true,
      "mock_database": true
    },
    "timestamp": "2026-10-01T17:11:37.713075"
  }
  ```

---

## 7. Deployment Instructions

### Deploying to Railway (Git Push)
1. Fork or push the repository to your GitHub account:
   ```bash
   git add .
   git commit -m "feat: complete DocShield single-container production architecture"
   git push origin main
   ```
2. In Railway:
   - Create a **New Project** -> **Deploy from GitHub repo**.
   - Select the `DocShield` repository.
   - Railway will automatically detect `railway.json` and build using `Dockerfile`.
3. In Railway **Variables**:
   - `DOCSHIELD_ENV` = `production`
   - `DOCSHIELD_MODE` = `PROTOTYPE`
   - `DOCSHIELD_OFFICER_KEY` = `[Generate a secure 32+ character random string]`
4. Verify the deployment:
   - Navigate to your public Railway domain: `https://docshield-production.up.railway.app/`.
   - Verify that the homepage loads, the legal notices are visible, and `/health` returns `200`.

### Local Docker Build & Verification
To test the production container locally:
```bash
# Build the Docker image
docker build -t docshield:latest .

# Run container on port 8000
docker run -p 8000:8000 -e DOCSHIELD_MODE=PROTOTYPE -e DOCSHIELD_ENV=production docshield:latest

# Verify endpoints
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

---

## 8. Verification & Compliance Checklist

- [x] Precompiled React frontend statically served from `/` and client routes.
- [x] Dynamic host port binding `${PORT:-8000}`.
- [x] Liveness (`/health`) and Readiness (`/ready`) endpoints configured.
- [x] Rate limiting (`10/min`) and concurrency semaphore (`MAX_CONCURRENT_ANALYSIS=2`) active.
- [x] Ephemeral image handling (`ENABLE_SOURCE_IMAGE_STORAGE=false`) enforced.
- [x] Mandatory public prototype notices and simulated registry disclosures displayed across UI.
