# DOCSHIELD SYSTEM ARCHITECTURE DESIGN SPECIFICATION
**Document Version:** 2.0.0  
**Status:** Approved Architectural Blueprint (Pre-Implementation)  
**Author:** Principal Software Architect & Senior DevSecOps Engineer  
**Target Systems:** Public Prototype, Cloud Container Environments (Railway/Render), Future Enterprise/Gov Deployments  

---

## 1. ARCHITECTURAL OVERVIEW & CORE PRINCIPLES

DocShield is a multi-layered identity document screening and forensic analysis platform. The revised architecture transitions the project from a fragile monolithic hackathon prototype into a **modular, secure-by-default, fail-safe, and verifiable enterprise-ready screening platform**.

### Core Architectural Principles
1. **Separation of Modes:** Strict runtime and UX boundaries between **Demo Mode**, **Public Prototype Mode**, and **Authorized Operational Mode**. The UI never presents synthetic or heuristic signals as authoritative state clearances.
2. **Defensive Signal States (Fail-Safe Biometrics & Forensics):** Every pipeline output carries an explicit `SignalState`:
   - `VERIFIED_SIGNAL`: Produced by a mathematically sound or audited high-confidence model.
   - `INDETERMINATE`: The evidence is noisy, occluded, or inconclusive.
   - `UNAVAILABLE`: The underlying service/dependency is down or failed.
   - `DEMO_SIGNAL`: Synthetic data or mock heuristic.
   No fallback algorithm (such as 2D template matching) may ever masquerade as a verified biometric match.
3. **Decoupled Service Pipeline:** Extraction, validation, forensics, biometrics, watchlist lookup, risk aggregation, and reporting are decoupled into independent services orchestrated through an async threadpool/worker layer.
4. **Abstracted Persistence Layer:** Decoupled storage using SQLAlchemy ORM supporting embedded SQLite (for zero-cost single-container prototypes) and PostgreSQL (for scalable enterprise deployments). Zero reliance on volatile Python process heap dictionaries.
5. **Zero-Trust Security & Privacy by Design:** Strict input sanitization (file size caps, decompression bomb protection), rate limiting, role-based access control (RBAC), automatic Aadhaar 8-digit PII redaction, ephemeral storage with TTL auto-purge, and audited logging.
6. **Single-Container Unification:** A unified multi-stage Docker build packaging Vite React SPA compilation and FastAPI ASGI backend, running seamlessly on dynamic `$PORT` under 512MB RAM without memory crashes or cold-start timeouts.

---

## 2. THE THREE OPERATING MODES

DocShield explicitly segregates execution behavior, data handling, and user interface indicators across three modes:

```
+---------------------------------------------------------------------------------------------------+
|                                  DOCSHIELD OPERATING MODES                                        |
+------------------------------------+----------------------------------+---------------------------+
| 1. DEMO MODE                       | 2. PUBLIC PROTOTYPE MODE         | 3. AUTHORIZED OPERATIONAL |
+------------------------------------+----------------------------------+---------------------------+
| Purpose:                           | Purpose:                         | Purpose:                  |
| - Fast testing & UI exploration    | - Controlled public showcase     | - Real border control &   |
| - Zero external dependencies       | - Real user document uploads     |   law enforcement         |
| - 100% offline predictability     | - Experimental local AI/CV       | - Authoritative registers |
+------------------------------------+----------------------------------+---------------------------+
| Data Source:                       | Data Source:                     | Data Source:              |
| - Synthetic pre-packaged datasets  | - Live user uploads (ephemeral)  | - Live high-res biometric |
| - Static simulated watchlist       | - 7-record prototype watchlist   | - UIDAI, Interpol I-24/7, |
| - Known pass/fail fixtures         | - Non-authoritative registries   |   National Visa Systems   |
+------------------------------------+----------------------------------+---------------------------+
| Biometric Engine:                  | Biometric Engine:                | Biometric Engine:         |
| - Pre-computed feature vectors or  | - Lightweight ONNX MobileFaceNet | - NIST FRVT certified deep|
|   mock comparison vectors          |   (Cosine similarity)            |   biometric ensemble      |
+------------------------------------+----------------------------------+---------------------------+
| Signal Classification:             | Signal Classification:           | Signal Classification:    |
| - Flagged as "DEMO_SIGNAL"         | - Flagged as "EXPERIMENTAL"      | - Legally verified audit  |
| - Prominent yellow banner in UI    | - Clear disclaimer in UI         |   trail with digital cert |
+------------------------------------+----------------------------------+---------------------------+
| PII Handling:                      | PII Handling:                    | PII Handling:             |
| - Fictitious identities only       | - RAM scrubbing, 1-hr disk TTL,  | - FIPS 140-2 encryption   |
|                                    |   automatic Aadhaar redaction    |   at rest, HSM key mgmt   |
+------------------------------------+----------------------------------+---------------------------+
```

### UI Transparency Banner
Every screen in the web application renders a persistent status header:
- **Demo Mode:** `[DEMO MODE: Synthetic sample data active. No real images processed.]` (Badge: Amber)
- **Public Prototype Mode:** `[PUBLIC PROTOTYPE: Experimental AI screening. NOT an official government verification system.]` (Badge: Blue)
- **Authorized Operational Mode:** `[AUTHORIZED OPERATIONAL: Connected to National Identity Registry. Official Use Only.]` (Badge: Emerald)

---

## 3. END-TO-END SYSTEM ARCHITECTURE DIAGRAM

```
+---------------------------------------------------------------------------------------------------+
|                                          CLIENT TIER (SPA)                                        |
|  React 18 + Vite (Tailwind CSS, Modular Component Tree, Lucide Icons, Axios v1 Client)            |
|  - Operating Mode Banner (Demo / Prototype / Operational)                                         |
|  - Drag-and-Drop Ingestion with Client-Side MIME & 8MB Size Enforcer                             |
|  - Live Progressive Verification Stepper (OCR -> Forensics -> Biometrics -> Risk)                 |
|  - Officer Review Dashboard with Audit Trail and Decision Override                                |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  | HTTPS POST /api/v1/verify (multipart/form-data)
                                                  | Security: Bearer JWT (Officer) / CSRF / Rate-Limited
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                  API GATEWAY & SECURITY PERIMETER                                 |
|  FastAPI (backend/main.py)                                                                        |
|  - Strict CORS Policy (Configurable whitelist; no wildcard credentials)                           |
|  - Security Headers Middleware (CSP, HSTS, X-Content-Type-Options, X-Frame-Options)               |
|  - SlowAPI Rate Limiter (e.g. 10 req/min per IP on /verify; 60 req/min on reads)                 |
|  - 10MB Request Body Limit & Magic Byte File Signature Verification (libmagic)                     |
|  - Image Decompression Bomb Safeguard (PIL.Image.MAX_IMAGE_PIXELS = 10,000,000)                   |
|  - Global Exception Interceptor (Catches all faults -> Structured RFC 7807 JSON Error)            |
+---------------------------------------------------------------------------------------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
+--------------------------------------------------+    +----------------------------------+
|            PERSISTENCE & REPOSITORY LAYER        |    |    PIPELINE ORCHESTRATION LAYER  |
|  SQLAlchemy 2.0 ORM                              |    |  PipelineManager (ThreadPoolExecutor)|
|  - Dialect: SQLite (Prototype) / Postgres (Prod) |    |  - Async non-blocking CPU dispatch|
|  - Tables: Cases, Documents, Travellers, Audits  |    |  - Parallel execution:           |
|  - Ephemeral Disk Storage Manager with 24-hr TTL |    |    (OCR + Tampering concurrently)|
|  - Aadhaar Masked Column Transformers            |    |  - Timeout Guard (15s per stage) |
+--------------------------------------------------+    +----------------------------------+
                                                                           |
                         +-------------------------------------------------+
                         |
       +-----------------+-----------------+-----------------+-----------------+
       |                                   |                 |                 |
       v                                   v                 v                 v
+---------------------+ +----------------------+ +------------------+ +-----------------------+
|  DOCUMENT INGESTION | |     OCR & FIELD      | | DIGITAL FORENSIC | |   FACIAL BIOMETRIC    |
|  & CLASSIFICATION   | |      EXTRACTION      | |   VERIFICATION   | |     VERIFICATION      |
| services/classifier | | services/ocr_service | | services/forensic| | services/biometric_   |
| - Aspect Ratio &    | | - Tesseract Engine   | | _service.py      | | service.py            |
|   Geometry Check    | - EasyOCR Fallback     | - Patch-level ELA  | - Ultra-Light Face ONNX |
| - Document Type:    | - Full ICAO Doc 9303   | - Edge & Gradient  |   Detector (3MB)        |
|   PASSPORT_TD3      |   (TD1, TD2, TD3)      |   Analysis (Text)  | - MobileFaceNet ONNX    |
|   ID_CARD_TD1       | - Aadhaar Masking:     | - Metadata & EXIF  |   Embeddings (15MB)     |
|   VISA_TD2          |   (XXXX-XXXX-1234)     |   Sanitization     | - Genuine Cosine Metric |
|   AADHAAR_CARD      | - Provenance & Bounding| - Signal State:    | - Zero cv2.matchTemplate|
|   UNKNOWN_DOC       |   Box Coordinates      |   VERIFIED / NOISE | - Signal State:         |
|                     | - Signal State         |   / INDETERMINATE  |   VERIFIED / NO_FACE    |
+---------------------+ +----------------------+ +------------------+ +-----------------------+
       |                                   |                 |                 |
       +-----------------+-----------------+-----------------+-----------------+
                         |
                         v
+---------------------------------------------------------------------------------------------------+
|                                  WATCHLIST & REGISTRY SERVICE                                     |
|  services/registry_service.py                                                                     |
|  - Mode-aware Registry Adapter (MockPrototypeRegistry -> InterpolAdapter -> DigilockerAdapter)   |
|  - Signal State: REGISTRY_MATCH | REGISTRY_CLEAR | REGISTRY_UNAVAILABLE (Never clears on down!)  |
+---------------------------------------------------------------------------------------------------+
                         |
                         v
+---------------------------------------------------------------------------------------------------+
|                                TRANSPARENT RISK AGGREGATION ENGINE                                |
|  services/risk_engine.py                                                                          |
|  - Configurable, Versioned Weight Matrix (scoring_rules_v1.json)                                  |
|  - Evidence Provenance Synthesis (Tracks exact origin of every signal)                            |
|  - Missing Signal Degradation: Never penalizes or clears blindly when a service is UNAVAILABLE    |
|  - Explanatory Audit Trail: Natural language rationale for border officers                        |
|  - Classification Tiers: CLEAR (0-24), REVIEW_REQUIRED (25-59), HIGH_RISK (60-100)               |
+---------------------------------------------------------------------------------------------------+
                         |
                         v
+---------------------------------------------------------------------------------------------------+
|                                   CASE REPOSITORY & AUDIT LOGGER                                  |
|  services/case_service.py                                                                         |
|  - Saves complete ScreeningResult to SQLite / PostgreSQL                                         |
|  - Logs immutable Officer Review Actions (Case ID, Officer ID, Decision, Timestamp, Notes)       |
|  - Cleans up ephemeral raw image files according to Data Retention Policy                        |
+---------------------------------------------------------------------------------------------------+
```

---

## 4. COMPONENT RESPONSIBILITIES & MODULE BOUNDARIES

To ensure maintainability and eliminate bloated files, business logic is distributed across clean single-responsibility modules:

### 1. Ingestion & Security Boundary (`backend/core/security.py`, `backend/core/config.py`)
- **Input Sanitization:** Checks file sizes (max 8MB), enforces allowed MIME types (`image/jpeg`, `image/png`, `image/webp`), and verifies magic header bytes to prevent disguised executables.
- **Decompression Bomb Protection:** Configures Pillow with `MAX_IMAGE_PIXELS = 10_000_000` to prevent memory exhaustion from crafted ultra-high-resolution images.
- **Authentication:** Enforces HTTP Bearer JWT tokens for administrative and officer endpoints. Public upload routes utilize client token bucket rate-limiting.

### 2. Document Classification (`backend/services/classifier_service.py`)
- Determines document class prior to extraction: `PASSPORT_TD3`, `NATIONAL_ID_TD1`, `VISA_TD2`, `AADHAAR_CARD`, or `UNKNOWN_GENERIC`.
- Evaluates document aspect ratio, presence of MRZ layout bands, and header keyword distributions.
- Prevents unclassified documents from skipping validation rules.

### 3. OCR & Field Extraction (`backend/services/ocr_service.py`)
- **Multi-Engine Pipeline:** Runs PyTesseract with explicit preprocessing (adaptive thresholding, Otsu binarization).
- **Correct Fallback Logic:** If Tesseract returns an empty string or low-confidence characters, automatically dispatches to EasyOCR (or secondary preprocessor).
- **ICAO Doc 9303 Support:** Implements complete parsing for:
  - **TD3 (Passports):** 2 lines of 44 characters.
  - **TD1 (ID Cards):** 3 lines of 30 characters.
  - **TD2 (Visas):** 2 lines of 36 characters.
- **Privacy Masking:** Enforces strict regex replacement of 12-digit Indian Aadhaar numbers: `\b\d{4}\s\d{4}\s(\d{4})\b` $\rightarrow$ `XXXX-XXXX-$1`.

### 4. Mathematical Validation Engine (`backend/services/validation_service.py`)
- **ICAO 7-3-1 Weighting:** Computes check digits on Document Number, Date of Birth, Expiration Date, and Composite MRZ string.
- **Verhoeff Algorithm:** Validates 12th checksum digit on Indian Aadhaar numbers.
- **Temporal Validity:** Flags expired credentials, documents issued in the future, or travellers below minimum travel age.

### 5. Digital Image Forensics (`backend/services/tampering_service.py`)
- **Patch-Based Error Level Analysis (ELA):** Divides image into semantic patches (photo area, MRZ zone, text fields). Computes localized compression residuals rather than global linear averages, preventing sharp text edges from triggering false alarms.
- **FFT High-Frequency Residuals:** Analyzes frequency spectrum anomalies indicative of copy-paste splices.
- **EXIF & Metadata Sanitization:** Inspects metadata for image editing software signatures (Photoshop, GIMP, Canva) and strips GPS/camera serial numbers before saving.

### 6. Facial Biometrics Service (`backend/services/biometric_service.py`)
- **Lightweight ONNX Pipeline:** Uses an Ultra-Light Face Detector ONNX model (~3MB) and MobileFaceNet ONNX feature extractor (~15MB). Operates purely on CPU in <100ms with <50MB RAM footprint.
- **Facial Landmark Alignment:** Aligns eyes and mouth horizontally before extracting 128-dimensional L2-normalized embedding vectors.
- **Mathematically Sound Cosine Distance:** Direct cosine similarity calculation:
  $$\text{Similarity} = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$$
- **ZERO cv2.matchTemplate:** `cv2.matchTemplate` is permanently banned. If face detection fails or person is absent, the system emits `SignalState.INDETERMINATE` with `FaceMatchStatus.NO_FACE_DETECTED`.

### 7. Watchlist & Identity Registry (`backend/services/registry_service.py`)
- Modular registry adapter pattern:
  - In **Demo/Prototype Mode**: Queries `backend/data/mock_database.json` and returns `Provenance.PROTOTYPE_MOCK`.
  - In **Operational Mode**: Dispatches asynchronous requests to Interpol / National Database APIs with mutual TLS (mTLS).
- If the registry connection times out or fails, it emits `SignalState.UNAVAILABLE`. **The system never interprets a failed registry lookup as a clean clearance.**

### 8. Evidence Aggregation & Risk Engine (`backend/services/risk_engine.py`)
- Aggregates all signals into an explainable composite risk report with clear provenance.
- Prioritizes national security threats over administrative faults:
  - Biometric Impersonation: Critical Severity (+65 base penalty).
  - Watchlist Hit: Critical Severity (+80 base penalty).
  - Expired Credential: Administrative Warning (+20 base penalty).
  - Missing OCR Signal: Inconclusive Flag (+15 penalty with `INDETERMINATE` flag).

---

## 5. PERSISTENCE & DATA STORAGE STRATEGY

### Architectural Decoupling: In-Memory Dict Elimination
The fragile `self._cases: Dict[str, ScreeningResult]` is entirely eliminated. DocShield adopts a unified SQLAlchemy 2.0 repository architecture:

```
+---------------------------------------------------------------------------------------------------+
|                                    DATA PERSISTENCE MODEL                                         |
+------------------------------------+----------------------------------+---------------------------+
| Entity                             | Attributes                       | Storage Mechanism         |
+------------------------------------+----------------------------------+---------------------------+
| ScreeningCase                      | case_id (UUID primary key)       | SQLite / PostgreSQL       |
|                                    | created_at (UTC Timestamp)       |                           |
|                                    | operating_mode (Enum)            |                           |
|                                    | overall_risk_score (Integer)     |                           |
|                                    | risk_tier (Enum)                 |                           |
|                                    | status (PENDING / REVIEWED)      |                           |
+------------------------------------+----------------------------------+---------------------------+
| EvidenceRecord                     | id, case_id (Foreign Key)        | SQLite / PostgreSQL       |
|                                    | category (OCR, BIO, ELA, DB)     |                           |
|                                    | signal_state (Enum)              |                           |
|                                    | raw_score (Float)                |                           |
|                                    | confidence (Float)               |                           |
|                                    | details (JSONB / JSON text)      |                           |
+------------------------------------+----------------------------------+---------------------------+
| OfficerAudit                       | id, case_id (Foreign Key)        | SQLite / PostgreSQL       |
|                                    | officer_id (String / JWT sub)    | (Append-Only Log)         |
|                                    | action (CLEARED / REJECTED)      |                           |
|                                    | reason_code, notes (Text)        |                           |
|                                    | timestamp (UTC)                  |                           |
+------------------------------------+----------------------------------+---------------------------+
| ImageArtifact                      | artifact_id, case_id             | Ephemeral File System     |
|                                    | file_path, sha256_hash           | (with 24-hr TTL purge)    |
|                                    | expires_at (UTC Timestamp)       | Never in RAM Heap         |
+------------------------------------+----------------------------------+---------------------------+
```

### Storage Engine Portability:
- **Default Prototype Deployment:** `sqlite+aiosqlite:///./data/docshield.db` (zero external dependencies, runs inside container volume).
- **Enterprise / Scalable Deployment:** Set `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/docshield`. The ORM models remain 100% identical.

### RAM Scrubbing & Disk TTL Purge:
- Uploaded images are written to a temp folder (`/tmp/docshield/uploads/{case_id}/`).
- Images are **never** held as Base64 strings in persistent database tables or process memory.
- A background scheduler cleans up files older than `RETENTION_HOURS` (Default: 1 hour for public prototype, 24 hours for demo).

---

## 6. DETAILED API SPECIFICATION (V1 REST)

All API endpoints reside under the `/api/v1` namespace.

### 1. Health & Readiness Probes
- `GET /api/v1/health`
  - **Purpose:** Kubernetes / Railway / Render lightweight liveness check.
  - **Response (200 OK):** `{"status": "pass", "version": "2.0.0", "mode": "PROTOTYPE"}`
  - **Latency:** < 5ms (no database or model queries).
- `GET /api/v1/readiness`
  - **Purpose:** Deep dependency readiness probe.
  - **Response (200 OK / 503 Service Unavailable):**
    ```json
    {
      "status": "ready",
      "checks": {
        "database": "connected",
        "onnx_biometrics": "loaded",
        "ocr_engine": "available",
        "disk_storage": "writable"
      }
    }
    ```

### 2. Document Verification
- `POST /api/v1/verify`
  - **Content-Type:** `multipart/form-data`
  - **Parameters:**
    - `document` (File, required, max 8MB, JPEG/PNG)
    - `traveller` (File, required, max 8MB, JPEG/PNG)
    - `mode` (String, optional: `DEMO`, `PROTOTYPE`)
  - **Rate Limit:** 10 requests / minute / IP
  - **Response Structure:**
    ```json
    {
      "case_id": "c7a8b9e1-4567-4a89-8d12-e3456789abcd",
      "timestamp": "2026-10-01T22:00:00Z",
      "operating_mode": "PUBLIC_PROTOTYPE",
      "document_classification": "PASSPORT_TD3",
      "signals": {
        "ocr": {
          "state": "VERIFIED_SIGNAL",
          "document_type": "PASSPORT",
          "document_number": "M12345678",
          "masked_aadhaar": null,
          "name": "DOE, JOHN",
          "nationality": "IND",
          "dob": "1988-04-12",
          "expiry": "2028-11-20",
          "mrz_valid": true
        },
        "forensics": {
          "state": "VERIFIED_SIGNAL",
          "tamper_detected": false,
          "ela_score": 18.4,
          "noise_variance": 4.2,
          "exif_flags": []
        },
        "biometrics": {
          "state": "VERIFIED_SIGNAL",
          "face_match": true,
          "similarity_score": 0.892,
          "model": "MobileFaceNet-ONNX-v1",
          "distance_metric": "cosine"
        },
        "watchlist": {
          "state": "DEMO_SIGNAL",
          "flagged": false,
          "registry_source": "Prototype Watchlist (7 Records)"
        }
      },
      "risk_assessment": {
        "composite_score": 12,
        "risk_tier": "CLEAR",
        "critical_flags": [],
        "mitigating_factors": ["VALID_MRZ_CHECKSUM", "HIGH_BIOMETRIC_CONFIDENCE"],
        "recommended_action": "ROUTINE_ADMISSION"
      }
    }
    ```

### 3. Case Review & Audit
- `GET /api/v1/cases`
  - **Security:** Requires `Authorization: Bearer <token>` (Officer role)
  - **Query Params:** `limit=50`, `offset=0`, `risk_tier=HIGH_RISK`
- `GET /api/v1/cases/{case_id}`
  - Returns complete case audit record and evidentiary breakdown.
- `POST /api/v1/cases/{case_id}/review`
  - **Security:** Requires `Authorization: Bearer <token>`
  - **Request Body:**
    ```json
    {
      "decision": "CLEARED",
      "reason_code": "SECONDARY_INSPECTION_SATISFIED",
      "notes": "Physical passport security holographic watermark verified manually."
    }
    ```

---

## 7. SIGNAL STATES & SAFE FAILURE BEHAVIOR MATRIX

Every service adheres strictly to safe degradation principles:

| Service / Step | Failure Condition | Signal State | Result Returned | Risk Engine Impact | UI Presentation |
|---|---|---|---|---|---|
| **OCR Service** | Low-contrast / blurry image; text unreadable | `INDETERMINATE` | `mrz_valid: false`, `extracted_fields: {}` | Flags `UNREADABLE_DOCUMENT` (+25 points); marks case for manual inspection | Displays amber warning: *"Text unreadable. Manual transcription required."* |
| **OCR Engine Crash** | Tesseract binary missing or segfault | `UNAVAILABLE` | `error: "OCR engine unavailable"` | Flags `SERVICE_DEGRADED` (+15 points); does NOT claim document valid | Displays red badge: *"OCR Subsystem Offline"* |
| **Forensics (ELA)** | Extreme image compression or non-JPEG | `INDETERMINATE` | `ela_score: null`, `tamper_detected: false` | Neutral impact; logs `FORENSICS_INCONCLUSIVE` | Displays: *"Compression artifacts prevent automated forensic analysis."* |
| **Face Detection** | No face visible in ID or selfie | `INDETERMINATE` | `face_match: null`, `status: "NO_FACE_DETECTED"` | Critical Alert: `BIOMETRIC_ABSENT` (+45 points); forces Officer Review | Displays: *"Face not detected in image. Cannot complete biometric match."* |
| **Biometric Model** | ONNX runtime failure or memory limit | `UNAVAILABLE` | `similarity_score: null` | Forces `SECONDARY_INSPECTION` (+40 points) | Displays: *"Biometric verification unavailable."* **Never falls back to pixel template matching!** |
| **Watchlist Service**| Database connection timeout or crash | `UNAVAILABLE` | `registry_hit: null`, `status: "OFFLINE"` | Flags `REGISTRY_CHECK_INCOMPLETE` (+30 points); **never auto-clears!** | Displays: *"National Registry unreachable. Admission clearance withheld."* |

---

## 8. SECURITY & PRIVACY SPECIFICATION

### 1. Indian Aadhaar Act (2016) Compliance Architecture
- Full 12-digit Aadhaar numbers are intercepted at the regex boundary in `ocr_service.py`.
- The first 8 digits are replaced with `XXXX-XXXX-` prior to instantiation of any Pydantic model.
- Raw Aadhaar numbers are never written to disk, SQLite, logs, or API responses.

### 2. Anti-Denial of Service (DoS) Controls
- **Upload Limit:** Starlette middleware rejects payloads exceeding 8MB with HTTP 413.
- **Decompression Bomb Guard:** PIL Pillow image allocation capped at 10 megapixels.
- **Async Threadpool Dispatch:** Heavy OpenCV matrix operations execute via `starlette.concurrency.run_in_threadpool`, preventing asyncio event-loop starvation.
- **Rate Limiting:** SlowAPI token bucket allows maximum 10 verification requests per minute per IP address.

### 3. Role-Based Access Control (RBAC)
- Public users can only execute `POST /api/v1/verify` and receive ephemeral session results.
- Endpoints `/api/v1/cases`, `/api/v1/cases/{case_id}/review`, and `/api/v1/admin/*` require verified JWT claims (`role: "border_officer"` or `role: "system_admin"`).

---

## 9. SINGLE-CONTAINER DEPLOYMENT ARCHITECTURE

To guarantee that DocShield deploys to Railway, Render, or a single virtual server with zero manual orchestration:

```
+---------------------------------------------------------------------------------------------------+
|                                  DOCKER CONTAINER BOUNDARY                                        |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | Multi-Stage Build Stage 1: Frontend Compiler (node:20-slim)                                 |  |
|  | - Run `npm install` && `npm run build` -> compiles React SPA into /app/frontend/dist        |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                                 | (Copies /dist assets)                           |
|                                                 v                                                 |
|  +---------------------------------------------------------------------------------------------+  |
|  | Multi-Stage Build Stage 2: Runtime Container (python:3.11-slim)                            |  |
|  | - System Packages: `tesseract-ocr`, `tesseract-ocr-eng`, `libgl1`, `libglib2.0-0`           |  |
|  | - Python Dependencies: `fastapi`, `uvicorn`, `onnxruntime`, `opencv-python-headless`,        |  |
|  |   `sqlalchemy`, `aiosqlite`, `pydantic`                                                     |  |
|  | - Stripped Dependencies: PyTorch, Torchvision, DeepFace removed (saves 2.8GB disk & RAM!)    |  |
|  | - Baked ONNX Models: /app/models/ultra_light_face.onnx & /app/models/mobilefacenet.onnx     |  |
|  |                                                                                             |  |
|  | ASGI Process: Uvicorn                                                                       |  |
|  | - Serves `/api/v1/*` routes dynamically                                                     |  |
|  | - Serves `/app/frontend/dist` as static assets for `/` and SPA fallback routes               |  |
|  | - Binds to dynamic environment variable `$PORT` (defaults to 8000)                          |  |
|  | - RAM Footprint: ~280MB peak (Safely under 512MB Railway Free Tier limit!)                  |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

## 10. FUTURE SCALING & AUTHORITATIVE GOVERNMENT INTEGRATION STRATEGY

When transitioning from the Public Prototype to Authorized Operational Mode, the modular architecture permits drop-in enhancements without refactoring core services:

```
                                  [AUTHORITATIVE INTEGRATION ROADMAP]

   +--------------------------+       +--------------------------+       +--------------------------+
   |   UIDAI AADHAAR AUTH     |       |    INTERPOL I-24/7 API   |       |   ICAO PKD CERTIFICATE   |
   | - e-KYC 2.0 Integration  |       | - Stolen and Lost Travel |       |   VALIDATION             |
   | - Biometric Hash Match   |       |   Document (SLTD) check  |       | - Cryptographic Chip Ver.|
   | - Registered Device SDK  |       | - Real-time Red Notice   |       | - CSCA Master List verify|
   +--------------------------+       +--------------------------+       +--------------------------+
                 |                                  |                                  |
                 +----------------------------------+----------------------------------+
                                                    |
                                                    v
                                  +------------------------------------+
                                  |    IDENTITY REGISTRY ADAPTER BUS   |
                                  |    (services/registry_service.py)  |
                                  +------------------------------------+
```

1. **DigiLocker / UIDAI Gateway:** Replace regex-based Aadhaar OCR with direct QR-code cryptographic signature verification or official DigiLocker OAuth2 consent-driven document pull.
2. **ICAO Public Key Directory (PKD):** Integrate NFC passport e-chip inspection to mathematically verify digital signatures against world government root CSCA certificates.
3. **Dedicated GPU Worker Cluster:** When scaling beyond 1,000 requests/minute, offload the PipelineManager from local ThreadPoolExecutor to a distributed Redis/Celery queue with autoscaling GPU worker pods.

---

## 11. PUBLIC DEMO LIMITATIONS & ETHICAL AI DISCLAIMER

The web application must embed the following legal and technical disclosures:
1. **Non-Authoritative Status:** The public prototype is an educational and engineering demonstration. It is not connected to live government databases and cannot be used as legal proof of identity.
2. **Biometric Ethical Guardrails:** All biometric face similarity computations are performed strictly in-memory during the ephemeral session; face crops are automatically scrubbed from memory after score computation.
3. **No Automated Detention Decisions:** The system provides decision-support evidence to human border officers. It never issues automated legal detention or admission rejection orders.
