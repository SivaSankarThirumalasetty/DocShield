import time
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Query, Request, Depends, Header, status
from PIL import Image

from ..core.config import settings
from ..core.logging import logger
from ..core.security import (
    validate_image_upload,
    verify_officer_token,
    mask_aadhaar_number,
    generate_session_token,
    sanitize_filename
)
from ..core.rate_limit import analysis_semaphore, rate_limit_analysis
from ..models.schemas import (
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
from ..utils.image_utils import (
    bytes_to_cv2,
    cv2_to_pil,
    cv2_to_base64,
    deskew,
    resize_if_larger
)
from ..services.ocr_service import ocr_service
from ..services.document_parser import document_parser
from ..services.validation_service import validation_service
from ..services.mock_database import db_service
from ..services.tampering_service import tampering_service
from ..services.face_service import face_service
from ..services.risk_engine import risk_engine
from ..services.storage_service import storage_service

router = APIRouter()

# ---------------------------------------------------------
# Health & Readiness Probes
# ---------------------------------------------------------

@router.get("/health")
async def liveness_probe():
    """Lightweight liveness probe: indicates process is responsive."""
    return {
        "status": "healthy",
        "service": "DocShield Border Screening Engine",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/ready")
async def readiness_probe():
    """Readiness probe: validates database connection and critical subsystem dependencies."""
    checks = {
        "database": False,
        "ocr_engine": ocr_service.is_engine_available,
        "face_detector": face_service.net is not None,
        "mock_database": len(db_service.data.get("watchlist", [])) > 0
    }
    
    try:
        storage_service.list_cases(limit=1)
        checks["database"] = True
    except Exception as e:
        logger.error(f"Readiness check: database failed: {e}")
        checks["database"] = False

    is_ready = checks["database"] and checks["mock_database"]
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "mode": settings.operating_mode,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """Backward-compatible health endpoint for React frontend."""
    return HealthResponse(
        status="healthy",
        service="DocShield Border Screening Engine",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat(),
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
            f"DocShield mode: {settings.operating_mode}.",
            "Persistent SQLite / SQLAlchemy storage active.",
            "Aadhaar 8-digit PII masking active."
        ]
    )

# ---------------------------------------------------------
# Document Analysis & Verification Pipeline
# ---------------------------------------------------------

@router.post(
    "/api/analyze-document",
    response_model=ScreeningResult,
    dependencies=[Depends(rate_limit_analysis)]
)
async def analyze_document(
    document: UploadFile = File(..., description="Document front scan or image"),
    person_image: Optional[UploadFile] = File(None, description="Optional live traveller camera/selfie"),
    doc_type_hint: Optional[str] = Form(None, description="Optional document type hint (e.g. AADHAAR, PASSPORT, PAN)")
):
    start_time = time.time()

    # Apply concurrency semaphore to protect CPU from saturation
    async with analysis_semaphore:
        # 1. Read and strictly validate document upload
        try:
            doc_bytes = await document.read()
        except Exception as e:
            logger.error(f"Failed to read document upload: {e}")
            raise HTTPException(status_code=400, detail="Failed to read document file upload.")

        # Sanitize filename & validate signature/dimensions
        clean_doc_name = sanitize_filename(document.filename)
        pil_doc_validated = validate_image_upload(doc_bytes, field_name=clean_doc_name)

        try:
            cv_doc = bytes_to_cv2(doc_bytes)
            cv_doc = resize_if_larger(cv_doc, max_dim=1600)
            cv_doc, skew_angle = deskew(cv_doc)
            pil_doc = cv2_to_pil(cv_doc)
        except Exception as e:
            logger.error(f"Document preprocessing failure: {e}")
            raise HTTPException(status_code=400, detail="Failed to process document image. Please upload a clear photo.")

        # 2. Ingest and strictly validate optional live person image
        cv_person = None
        person_b64 = None
        if person_image is not None and person_image.filename:
            try:
                person_bytes = await person_image.read()
                if len(person_bytes) > 0:
                    clean_person_name = sanitize_filename(person_image.filename)
                    validate_image_upload(person_bytes, field_name=clean_person_name)
                    cv_person = bytes_to_cv2(person_bytes)
                    cv_person = resize_if_larger(cv_person, max_dim=1200)
                    person_b64 = cv2_to_base64(cv_person, quality=80)
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Failed to process person image: {e}")

        # 3. Optical Character Recognition (OCR)
        try:
            ocr_result = ocr_service.extract_text(pil_doc)
        except Exception as e:
            logger.error(f"OCR extraction exception: {e}")
            ocr_result = {"engine": "error_fallback", "raw_text": "", "words": [], "success": False}

        # 4. Structured Field Parsing & Classification
        try:
            doc_info = document_parser.parse(ocr_result, doc_type_hint=doc_type_hint)
        except Exception as e:
            logger.error(f"Document parsing error: {e}")
            doc_info = ExtractedFields(document_type="UNKNOWN", raw_text_preview="")

        # 5. Document Validation & Checksum Verification
        try:
            validation_res = validation_service.validate_document(doc_info)
        except Exception as e:
            logger.error(f"Validation calculation error: {e}")
            validation_res = ValidationResult(
                overall_valid=False,
                checks_passed=0,
                checks_total=1,
                checks=[ValidationFlag(check_name="Validation Error", field="SYSTEM", passed=False, message="Validation logic error", severity="warning")]
            )

        # 6. Mock Database & Watchlist Query
        try:
            watchlist_res = db_service.check_watchlist(name=doc_info.name, doc_number=doc_info.document_number)
        except Exception as e:
            logger.error(f"Watchlist lookup error: {e}")
            watchlist_res = WatchlistHit(is_flagged=False, status="UNAVAILABLE", details="Database lookup failed.")

        # 7. Error Level Analysis & Tampering Forensics
        try:
            tamper_res = tampering_service.analyze(pil_doc)
        except Exception as e:
            logger.error(f"Forensics analysis error: {e}")
            tamper_res = TamperAnalysisResult(
                ela_score=0.0,
                has_anomalies=False,
                anomaly_regions=0,
                bounding_boxes=[],
                forensic_notes=["Forensic analysis unavailable"]
            )

        # 8. Biometric Face Verification
        try:
            face_res = face_service.verify_faces(cv_doc, cv_person)
        except Exception as e:
            logger.error(f"Face verification error: {e}")
            face_res = FaceVerificationResult(
                document_face_detected=False,
                person_face_detected=False,
                similarity_score=0.0,
                match_verdict="INDETERMINATE",
                notes="Biometric verification failed"
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
            logger.error(f"Risk evaluation error: {e}")
            risk_res = RiskAssessment(
                score=50,
                level="MEDIUM",
                verdict="SECONDARY_INSPECTION",
                reasons=["Automated risk scoring notice: Evaluation error"],
                breakdown={}
            )

        # 10. Cryptographic Case ID & Session Token Generation
        elapsed_ms = round((time.time() - start_time) * 1000.0, 1)
        case_id = f"DS-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        raw_session_token, session_token_hash = generate_session_token()

        case = ScreeningResult(
            case_id=case_id,
            timestamp=datetime.utcnow().isoformat(),
            processing_time_ms=elapsed_ms,
            document_info=doc_info,
            validation=validation_res,
            watchlist=watchlist_res,
            tampering=tamper_res,
            face_verification=face_res,
            risk_assessment=risk_res,
            document_preview_base64=cv2_to_base64(cv_doc, quality=80),
            person_preview_base64=person_b64,
            session_token=raw_session_token
        )

        # 11. Persist to storage with session token hash
        try:
            storage_service.save_case(case, session_token_hash=session_token_hash)
        except Exception as e:
            logger.error(f"Case persistence failed: {e}")

        # Raw document bytes and cv matrices are freed as function scope closes
        del doc_bytes
        if cv_person is not None:
            del cv_person

        return case

@router.post(
    "/api/verify-face",
    response_model=FaceVerifyResponse,
    dependencies=[Depends(rate_limit_analysis)]
)
async def verify_face(
    image1: UploadFile = File(..., description="First face image (e.g. ID card portrait)"),
    image2: UploadFile = File(..., description="Second face image (e.g. Live camera capture)")
):
    async with analysis_semaphore:
        try:
            b1 = await image1.read()
            b2 = await image2.read()
            validate_image_upload(b1, field_name=sanitize_filename(image1.filename))
            validate_image_upload(b2, field_name=sanitize_filename(image2.filename))
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
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Face verify endpoint error: {e}")
            raise HTTPException(status_code=400, detail="Face verification failed. Please upload clear face images.")

# ---------------------------------------------------------
# Case Records & Officer Review (Authorized Access)
# ---------------------------------------------------------

@router.get("/api/case/{case_id}", response_model=ScreeningResult)
async def get_case(
    case_id: str,
    x_session_token: Optional[str] = Header(None),
    x_officer_key: Optional[str] = Header(None)
):
    """
    Authorized case retrieval:
    Requires matching X-Session-Token (submitter) OR X-Officer-Key (officer).
    Prevents unauthorized browsing and case ID enumeration.
    """
    is_officer = bool(x_officer_key and x_officer_key == settings.officer_key)
    case, auth_status = storage_service.get_case_with_auth(
        case_id=case_id,
        session_token=x_session_token,
        is_officer=is_officer
    )

    if auth_status == "FORBIDDEN":
        logger.warning(f"Unauthorized case access attempt on {case_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Valid session token or officer authorization required."
        )

    if auth_status == "NOT_FOUND" or not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case ID '{case_id}' not found."
        )

    return case

@router.get("/api/cases", response_model=List[CaseSummary])
async def list_cases(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    officer_token: str = Depends(verify_officer_token)
):
    """Officer-only endpoint: lists screening case summaries with audit trail."""
    return storage_service.list_cases(limit=limit, offset=offset)

@router.post("/api/case/{case_id}/review", response_model=ScreeningResult)
async def submit_officer_review(
    case_id: str,
    payload: OfficerReviewRequest,
    officer_token: str = Depends(verify_officer_token)
):
    """Officer-only endpoint: records official clearance or rejection decision."""
    case_record = storage_service.get_case_record(case_id)
    if not case_record:
        raise HTTPException(status_code=404, detail=f"Case ID '{case_id}' not found")
    
    review = OfficerReview(
        reviewed=True,
        officer_id=payload.officer_id,
        officer_name=payload.officer_name,
        decision=payload.decision,
        override_ai_verdict=payload.override_ai_verdict,
        notes=payload.notes,
        timestamp=datetime.utcnow().isoformat()
    )
    
    updated_case = storage_service.update_officer_review(case_id, review)
    if not updated_case:
        raise HTTPException(status_code=500, detail="Failed to record officer review.")
    return updated_case

# ---------------------------------------------------------
# Diagnostic Endpoint (Protected / Conditional)
# ---------------------------------------------------------

@router.get("/api/debug")
async def debug_info(x_officer_key: Optional[str] = Header(None)):
    """Diagnostics endpoint. Strictly requires debug enabled and officer authorization."""
    if not settings.enable_debug_endpoint:
        raise HTTPException(status_code=404, detail="Not Found")
    
    if not x_officer_key or x_officer_key != settings.officer_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    import sys
    return {
        "status": "diagnostic_active",
        "python_version": sys.version.split()[0],
        "environment": settings.app_env,
        "operating_mode": settings.operating_mode,
        "tesseract_configured": ocr_service.tesseract_configured,
        "caffe_loaded": face_service.net is not None
    }
