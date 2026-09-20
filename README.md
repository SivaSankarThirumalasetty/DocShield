# DocShield: AI-Based Fake Identity & Document Screening System
**Smart India Hackathon 2026** | **Problem Statement:** SIH26188  
**Organization:** Ministry of Home Affairs (MHA) | **Department:** Sashastra Seema Bal (SSB)

DocShield is a standalone, AI-powered identity and travel document screening system tailored for border security checkposts, immigration checkpoints, and law enforcement agencies.

---

## Target Workflow

`
Document Image + Person Live Photo
               │
               ▼
   [ Document Preprocessing ]  (Deskewing, Binarization, Contrast Tuning)
               │
               ▼
   [ Document Classification ]  (Aadhaar, Passport, PAN, Voter ID)
               │
               ▼
       [ OCR Text Extraction ]  (Character & Word Bounding Boxes)
               │
               ▼
   [ Structured Field Parsing ] (ID No., Name, DOB, Gender, Expiry, MRZ)
               │
               ▼
    [ Validation & Checksums ]  (Verhoeff 12-digit algorithm, Regex formats, Dates)
               │
               ▼
   [ Mock SSB Registry Check ]  (Look-out circulars, Stolen/Lost database, Impersonators)
               │
               ▼
   [ Tamper Analysis (ELA) ]    (Error Level Analysis, Compression Discrepancy Heatmap)
               │
               ▼
    [ Face Verification 1:1 ]   (OpenCV DNN Caffe SSD + 128-d Face Embedding Distance)
               │
               ▼
     [ Multi-Factor Risk ]      (0 - 100 Risk Score: LOW / MEDIUM / HIGH)
               │
               ▼
   [ Explainable Reasons ]      (Human-readable forensic audit reasons)
               │
               ▼
    [ Officer Web Dashboard ]   (Dual-panel intake & forensic dossier display)
`

---

## Directory Structure

`
DocShield/
├── backend/
│   ├── main.py                     # FastAPI application entrypoint & routing
│   ├── requirements.txt            # Python dependencies
│   ├── services/
│   │   ├── ocr_service.py          # Optical character recognition & bounding boxes
│   │   ├── document_parser.py      # Document classification & entity parsing
│   │   ├── validation_service.py   # Checksums (Verhoeff for Aadhaar), format regex, dates
│   │   ├── tampering_service.py    # In-memory Error Level Analysis (ELA) & heatmap
│   │   ├── face_service.py         # OpenCV DNN SSD face detector & biometric matching
│   │   ├── risk_engine.py          # Multi-signal weighted risk score & explainability
│   │   ├── mock_database.py        # Simulated SSB registry, stolen ID, and watchlist lookups
│   │   └── report_service.py       # Case persistence & audit history
│   ├── models/
│   │   └── schemas.py              # Pydantic data schemas for requests & responses
│   ├── utils/
│   │   └── image_utils.py          # Image loading, deskewing, base64 encoding
│   ├── data/
│   │   └── mock_database.json      # Mock database records
│   └── models_weights/             # Pre-trained OpenCV Caffe SSD weights
│       ├── deploy.prototxt
│       └── res10_300x300_ssd_iter_140000_fp16.caffemodel
│
├── frontend/                       # Modern React + Vite Officer Screening Dashboard
│   ├── src/
│   │   ├── App.jsx                 # Screening station & forensic dossier interface
│   │   ├── api.js                  # Client communicating with FastAPI endpoints
│   │   └── index.css               # Border security dark UI theme
│   ├── package.json
│   └── vite.config.js              # Configured with proxy to backend
│
├── sample_data/                    # Sample scenarios for demo and testing
├── reports/                        # Target directory for generated inspection dockets
├── source_references/              # Attributions & reference mappings
├── run_local.bat                   # Single-click launcher for Windows
└── README.md
`

---

## Getting Started (Local Execution)

### Option 1: One-Click Windows Launcher
Double-click 
un_local.bat in the root directory:
`cmd
run_local.bat
`
This automatically starts:
- FastAPI backend on http://127.0.0.1:8000
- React Vite Dashboard on http://localhost:5173

---

### Option 2: Manual Terminal Execution

#### 1. Start Backend:
`ash
cd backend
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
`
API Documentation will be accessible at: http://127.0.0.1:8000/docs

#### 2. Start Frontend:
`ash
cd frontend
npm run dev
`
Officer Dashboard will be accessible at: http://localhost:5173

---

## Core API Endpoints

- **GET /api/health**: Real-time status of backend services and modules.
- **POST /api/analyze-document**: Accepts multipart form data with document (image), optional person_image (selfie), and optional doc_type_hint. Executes complete screening pipeline and returns structured JSON dossier.
- **POST /api/verify-face**: Compares two face images and returns similarity percentage and match verdict.
- **GET /api/case/{case_id}**: Retrieves stored case details by ID.
- **GET /api/cases**: Lists recent screening cases.

---

## Third-Party Attributions & License
This application uses algorithms and models adapted from:
- document-forger (MIT License)
- idcard-face-match (MIT License)
- FakeImageDetector / AWS Document Tampering references (MIT-0 / MIT)
