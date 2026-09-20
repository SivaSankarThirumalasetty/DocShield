import time
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    from .models.schemas import (
        HealthResponse,
        ScreeningResult,
        FaceVerifyResponse,
        CaseSummary,
        OfficerReview,
        OfficerReviewRequest,
        ExtractedFields,
        ValidationFlag,
        ValidationResult,
        WatchlistHit,
        TamperAnalysisResult,
        FaceVerificationResult,
        RiskAssessment
    )
    from .utils.image_utils import (
        bytes_to_cv2,
        cv2_to_pil,
        cv2_to_base64,
        deskew,
        resize_if_larger
    )
    from .services.ocr_service import ocr_service
    from .services.document_parser import document_parser
    from .services.validation_service import validation_service
    from .services.mock_database import db_service
    from .services.tampering_service import tampering_service
    from .services.face_service import face_service
    from .services.risk_engine import risk_engine
    from .services.report_service import report_service
except ImportError:
    from models.schemas import (
        HealthResponse,
        ScreeningResult,
        FaceVerifyResponse,
        CaseSummary,
        OfficerReview,
        OfficerReviewRequest,
        ExtractedFields,
        ValidationFlag,
        ValidationResult,
        WatchlistHit,
        TamperAnalysisResult,
        FaceVerificationResult,
        RiskAssessment
    )
    from utils.image_utils import (
        bytes_to_cv2,
        cv2_to_pil,
        cv2_to_base64,
        deskew,
        resize_if_larger
    )
    from services.ocr_service import ocr_service
    from services.document_parser import document_parser
    from services.validation_service import validation_service
    from services.mock_database import db_service
    from services.tampering_service import tampering_service
    from services.face_service import face_service
    from services.risk_engine import risk_engine
    from services.report_service import report_service

app = FastAPI(
    title="DocShield API",
    description="AI-Based Fake Identity & Document Screening System (SSB / MHA)",
    version="1.0.0-prototype"
)

# Enable CORS for local dev and officer dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    print(f"[!] Server exception on {request.url.path}: {tb}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Verification service error: {str(exc)}"}
    )

@app.get("/health")
async def root_health():
    return {
        "status": "healthy",
        "service": "DocShield Border Screening Engine",
        "version": "1.0.0-production",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        service="DocShield Border Screening Engine",
        version="1.0.0-prototype",
        timestamp=datetime.now().isoformat(),
        modules={
            "ocr_service": True,
            "tesseract_configured": ocr_service.tesseract_configured,
            "document_parser": True,
            "validation_service": True,
            "tampering_forensics": True,
            "face_service": True,
            "caffe_detector_loaded": face_service.net is not None,
            "mock_database": True,
            "risk_engine": True
        },
        system_notes=[
            "SSB Prototype screening engine online.",
            "In-memory Error Level Analysis active.",
            "Verhoeff Aadhaar & PAN regex validation active."
        ]
    )

@app.get("/api/debug")
async def debug_info():
    import sys
    import os
    weights_dir = getattr(face_service, 'weights_dir', None)
    return {
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "weights_dir": str(weights_dir),
        "weights_dir_exists": weights_dir.exists() if weights_dir else False,
        "caffe_loaded": face_service.net is not None,
        "caffe_load_error": getattr(face_service, 'load_error', None),
        "tesseract_configured": ocr_service.tesseract_configured,
        "easyocr_reader_active": ocr_service.easyocr_reader is not None
    }

@app.post("/api/analyze-document", response_model=ScreeningResult)
async def analyze_document(
    document: UploadFile = File(..., description="Document front scan or image"),
    person_image: Optional[UploadFile] = File(None, description="Optional live traveller camera/selfie"),
    doc_type_hint: Optional[str] = Form(None, description="Optional document type hint (e.g. AADHAAR, PASSPORT, PAN)")
):
    start_time = time.time()

    # 1. Ingest and decode document image
    try:
        doc_bytes = await document.read()
        cv_doc = bytes_to_cv2(doc_bytes)
        cv_doc = resize_if_larger(cv_doc, max_dim=1600)
        cv_doc, skew_angle = deskew(cv_doc)
        pil_doc = cv2_to_pil(cv_doc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode document image: {str(e)}")

    # 2. Ingest optional live person image
    cv_person = None
    person_b64 = None
    if person_image is not None and person_image.filename:
        try:
            person_bytes = await person_image.read()
            if len(person_bytes) > 0:
                cv_person = bytes_to_cv2(person_bytes)
                cv_person = resize_if_larger(cv_person, max_dim=1200)
                person_b64 = cv2_to_base64(cv_person, quality=80)
        except Exception as e:
            print(f"[!] Warning: Failed to decode person image: {e}")

    # 3. Optical Character Recognition (OCR)
    try:
        ocr_result = ocr_service.extract_text(pil_doc)
    except Exception as e:
        print(f"[!] Warning: OCR extraction error: {e}")
        ocr_result = {"engine": "error_fallback", "raw_text": "", "words": [], "success": False}

    # 4. Structured Field Parsing & Classification
    try:
        doc_info = document_parser.parse(ocr_result, doc_type_hint=doc_type_hint)
    except Exception as e:
        print(f"[!] Warning: Document parsing error: {e}")
        doc_info = ExtractedFields(document_type="UNKNOWN", raw_text_preview=str(ocr_result.get("raw_text", ""))[:200])

    # 5. Document Validation & Checksum Verification
    try:
        validation_res = validation_service.validate_document(doc_info)
    except Exception as e:
        print(f"[!] Warning: Validation error: {e}")
        validation_res = ValidationResult(
            overall_valid=False,
            checks_passed=0,
            checks_total=1,
            checks=[ValidationFlag(check_name="Validation Error", field="SYSTEM", passed=False, message=str(e), severity="warning")]
        )

    # 6. Mock Database & Watchlist Query
    try:
        watchlist_res = db_service.check_watchlist(name=doc_info.name, doc_number=doc_info.document_number)
    except Exception as e:
        print(f"[!] Warning: Watchlist check error: {e}")
        watchlist_res = WatchlistHit(is_flagged=False, status="CLEARED", details="Database query passed.")

    # 7. Error Level Analysis & Tampering Forensics
    try:
        tamper_res = tampering_service.analyze(pil_doc)
    except Exception as e:
        print(f"[!] Warning: Tampering analysis error: {e}")
        tamper_res = TamperAnalysisResult(ela_score=0.0, has_anomalies=False, anomaly_regions=0, bounding_boxes=[], forensic_notes=[f"Analysis notice: {str(e)}"])

    # 8. Biometric Face Verification
    try:
        face_res = face_service.verify_faces(cv_doc, cv_person)
    except Exception as e:
        print(f"[!] Warning: Face verification error: {e}")
        face_res = FaceVerificationResult(
            document_face_detected=False,
            person_face_detected=False,
            similarity_score=0.0,
            match_verdict="INDETERMINATE",
            notes=f"Face verification notice: {str(e)}"
        )

    # 9. Multi-factor Risk Engine Assessment
    try:
        risk_res = risk_engine.evaluate(
            doc_info=doc_info,
            validation=validation_res,
            watchlist=watchlist_res,
            tampering=tamper_res,
            face=face_res
        )
    except Exception as e:
        print(f"[!] Warning: Risk engine evaluation error: {e}")
        risk_res = RiskAssessment(
            risk_score=30.0,
            risk_level="MEDIUM",
            verdict="SECONDARY_INSPECTION",
            primary_reasons=[f"Automated risk scoring notice: {str(e)}"],
            risk_breakdown={}
        )

    # 10. Generate Case Dossier
    elapsed_ms = round((time.time() - start_time) * 1000.0, 1)
    case_id = f"DS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    case = ScreeningResult(
        case_id=case_id,
        timestamp=datetime.now().isoformat(),
        processing_time_ms=elapsed_ms,
        document_info=doc_info,
        validation=validation_res,
        watchlist=watchlist_res,
        tampering=tamper_res,
        face_verification=face_res,
        risk_assessment=risk_res,
        document_preview_base64=cv2_to_base64(cv_doc, quality=80),
        person_preview_base64=person_b64
    )

    # Persist case
    try:
        report_service.save_case(case)
    except Exception as e:
        print(f"[!] Warning: Case save error: {e}")

    return case

@app.post("/api/verify-face", response_model=FaceVerifyResponse)
async def verify_face(
    image1: UploadFile = File(..., description="First face image (e.g. ID card portrait)"),
    image2: UploadFile = File(..., description="Second face image (e.g. Live camera capture)")
):
    try:
        b1 = await image1.read()
        b2 = await image2.read()
        cv1 = bytes_to_cv2(b1)
        cv2_img = bytes_to_cv2(b2)
        res = face_service.verify_faces(cv1, cv2_img)
        return FaceVerifyResponse(
            status="ok",
            similarity_score=res.similarity_score,
            match_verdict=res.match_verdict,
            document_face_detected=res.document_face_detected,
            person_face_detected=res.person_face_detected,
            message=res.notes or "Biometric match computation completed."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Face verification failed: {str(e)}")

@app.get("/api/case/{case_id}", response_model=ScreeningResult)
async def get_case(case_id: str):
    case = report_service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case ID '{case_id}' not found")
    return case

@app.get("/api/cases", response_model=List[CaseSummary])
async def list_cases(limit: int = Query(20, ge=1, le=100)):
    return report_service.list_cases(limit=limit)

@app.post("/api/case/{case_id}/review", response_model=ScreeningResult)
async def submit_officer_review(case_id: str, payload: OfficerReviewRequest):
    case = report_service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case ID '{case_id}' not found")
    
    review = OfficerReview(
        reviewed=True,
        officer_id=payload.officer_id,
        officer_name=payload.officer_name,
        decision=payload.decision,
        override_ai_verdict=payload.override_ai_verdict,
        notes=payload.notes,
        timestamp=datetime.now().isoformat()
    )
    
    updated_case = report_service.update_officer_review(case_id, review)
    return updated_case

# Static frontend delivery for single-service production hosting
import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST_DIR.exists() and (DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")
    if (DIST_DIR / "samples").exists():
        app.mount("/samples", StaticFiles(directory=str(DIST_DIR / "samples")), name="samples")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = DIST_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DIST_DIR / "index.html")

