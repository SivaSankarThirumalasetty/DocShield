import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Query, Depends, Header, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ..core.config import settings
from ..core.logging import logger
from ..core.security import (
    validate_image_upload,
    verify_officer_token,
    is_valid_officer_key,
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
    RiskAssessment,
    PipelineStage,
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
from ..services import face_service as face_module
from ..services.face_service import face_service
from ..services.risk_engine import risk_engine
from ..services.storage_service import storage_service

router = APIRouter()

APP_VERSION = "2.1.0"
ALLOWED_DOC_HINTS = {"AADHAAR", "PAN", "PASSPORT", "VOTER_ID"}
# How long a request may wait for a free analysis slot before being turned away.
QUEUE_WAIT_SECONDS = 20.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def readiness_checks() -> dict:
    """Real dependency checks. Each value reports whether the component is usable now."""
    ocr = ocr_service.status()
    checks = {
        "ocr_tesseract": ocr["tesseract"],
        "ocr_easyocr": ocr["easyocr_loaded"],
        "face_detector": face_service.net is not None,
        "face_embedding": face_module.FACE_REC_AVAILABLE,
        "demo_registry": db_service.is_loaded,
    }
    required = ["ocr_tesseract", "face_detector", "demo_registry"]
    if settings.require_full_pipeline:
        required += ["ocr_easyocr", "face_embedding"]
    if storage_service is not None:
        try:
            storage_service.list_cases(limit=1)
            checks["database"] = True
        except Exception:
            checks["database"] = False
        required.append("database")
    return {"checks": checks, "required": required, "ready": all(checks[k] for k in required)}

# ---------------------------------------------------------
# Health & Readiness Probes
# ---------------------------------------------------------

@router.get("/health")
async def liveness_probe():
    """Liveness only: the process is up and serving HTTP. Says nothing about models."""
    return {"status": "alive", "version": APP_VERSION, "timestamp": _now()}

@router.get("/ready")
@router.get("/api/ready")
async def readiness_probe():
    """Readiness: 200 only when every required OCR / CV / registry dependency is usable."""
    result = readiness_checks()
    return JSONResponse(
        status_code=status.HTTP_200_OK if result["ready"] else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ready" if result["ready"] else "not_ready",
            "mode": settings.operating_mode,
            "checks": result["checks"],
            "required": result["required"],
            "timestamp": _now(),
        },
    )

@router.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """Liveness plus the actual state of each module (no hard-coded values)."""
    result = readiness_checks()
    return HealthResponse(
        status="healthy" if result["ready"] else "degraded",
        version=APP_VERSION,
        timestamp=_now(),
        modules=result["checks"],
        system_notes=[
            f"Mode: {settings.operating_mode}. Advisory prototype; not a government verification service.",
            "Registry checks use a SIMULATED 7-record DEMO dataset.",
            f"Case persistence: {'local SQLite' if storage_service is not None else 'handled by the Cloudflare Worker (D1)'}.",
        ]
    )

# ---------------------------------------------------------
# Document Analysis & Verification Pipeline
# ---------------------------------------------------------

async def _acquire_slot():
    try:
        await asyncio.wait_for(analysis_semaphore.acquire(), timeout=QUEUE_WAIT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The screening engine is busy. Please retry shortly.",
            headers={"Retry-After": "15"},
        )


@router.post(
    "/api/analyze-document",
    response_model=ScreeningResult,
    dependencies=[Depends(rate_limit_analysis)]
)
async def analyze_document(
    document: UploadFile = File(..., description="Document front scan or image"),
    person_image: Optional[UploadFile] = File(None, description="Optional person photo for face comparison"),
    doc_type_hint: Optional[str] = Form(None, description="Optional document type hint (AADHAAR, PASSPORT, PAN, VOTER_ID)")
):
    hint = (doc_type_hint or "").strip().upper() or None
    if hint is not None and hint not in ALLOWED_DOC_HINTS:
        raise HTTPException(status_code=422, detail="Unsupported doc_type_hint.")

    await _acquire_slot()
    try:
        return await _run_pipeline(document, person_image, hint)
    finally:
        analysis_semaphore.release()


async def _run_pipeline(document: UploadFile, person_image: Optional[UploadFile], hint: Optional[str]) -> ScreeningResult:
    start_time = time.time()
    stages: List[PipelineStage] = []

    # 1. Read and strictly validate document upload
    try:
        doc_bytes = await document.read(settings.max_upload_size_bytes + 1)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read document file upload.")
    validate_image_upload(doc_bytes, field_name=sanitize_filename(document.filename))

    try:
        cv_doc = bytes_to_cv2(doc_bytes)
        cv_doc = resize_if_larger(cv_doc, max_dim=1600)
        cv_doc, _ = deskew(cv_doc)
        pil_doc = cv2_to_pil(cv_doc)
    except Exception as e:
        logger.error(f"Document preprocessing failure: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="Failed to process document image. Please upload a clear photo.")
    del doc_bytes
    stages.append(PipelineStage(stage="image_decoding", status="COMPLETED"))

    # 2. Optional person image (validated with the same rules as the document)
    cv_person = None
    person_b64 = None
    if person_image is not None and person_image.filename:
        person_bytes = await person_image.read(settings.max_upload_size_bytes + 1)
        if len(person_bytes) > 0:
            validate_image_upload(person_bytes, field_name=sanitize_filename(person_image.filename))
            try:
                cv_person = resize_if_larger(bytes_to_cv2(person_bytes), max_dim=1200)
                person_b64 = cv2_to_base64(cv_person, quality=80)
            except Exception as e:
                logger.warning(f"Failed to process person image: {type(e).__name__}")
                raise HTTPException(status_code=400, detail="Failed to process person image.")
        del person_bytes

    # 3. OCR
    try:
        ocr_result = await run_in_threadpool(ocr_service.extract_text, pil_doc)
        if ocr_result.get("success"):
            stages.append(PipelineStage(stage="ocr", status="COMPLETED", detail=f"engine={ocr_result.get('engine')}"))
        elif not ocr_service.is_engine_available:
            stages.append(PipelineStage(stage="ocr", status="UNAVAILABLE", detail="No OCR engine is installed or loaded."))
        else:
            stages.append(PipelineStage(stage="ocr", status="FAILED", detail="OCR ran but found no legible text."))
    except Exception as e:
        logger.error(f"OCR extraction exception: {type(e).__name__}")
        ocr_result = {"engine": "error", "raw_text": "", "words": [], "ocr_confidence": 0.0, "success": False}
        stages.append(PipelineStage(stage="ocr", status="UNAVAILABLE", detail="OCR engine error."))

    # 4. Classification & field parsing
    try:
        doc_info = document_parser.parse(ocr_result, doc_type_hint=hint)
        stages.append(PipelineStage(stage="classification_and_parsing", status="COMPLETED",
                                    detail=f"document_type={doc_info.document_type}"))
    except Exception as e:
        logger.error(f"Document parsing error: {type(e).__name__}")
        doc_info = ExtractedFields(document_type="UNKNOWN", raw_text_preview="", evidence_state="UNAVAILABLE")
        stages.append(PipelineStage(stage="classification_and_parsing", status="UNAVAILABLE"))

    # 5. Format / checksum / date validation
    try:
        validation_res = validation_service.validate_document(doc_info)
        stages.append(PipelineStage(stage="format_and_checksum_validation", status="COMPLETED",
                                    detail=f"{validation_res.checks_passed}/{validation_res.checks_total} checks passed"))
    except Exception as e:
        logger.error(f"Validation calculation error: {type(e).__name__}")
        validation_res = ValidationResult(
            overall_valid=False, checks_passed=0, checks_total=1,
            checks=[ValidationFlag(check_name="Validation Error", field="SYSTEM", passed=False,
                                   message="Validation could not be completed.", severity="critical",
                                   evidence_state="UNAVAILABLE")]
        )
        stages.append(PipelineStage(stage="format_and_checksum_validation", status="UNAVAILABLE"))

    # 6. Simulated (DEMO) registry lookup
    try:
        watchlist_res = db_service.check_watchlist(name=doc_info.name, doc_number=doc_info.document_number)
    except Exception as e:
        logger.error(f"Watchlist lookup error: {type(e).__name__}")
        watchlist_res = WatchlistHit(is_flagged=False, status="UNAVAILABLE",
                                     details="[DEMO_WATCHLIST] Lookup failed.", evidence_state="UNAVAILABLE")
    stages.append(PipelineStage(
        stage="simulated_registry_check",
        status="UNAVAILABLE" if watchlist_res.status == "UNAVAILABLE" else "COMPLETED",
        detail="SIMULATED demo dataset; not a real registry.",
    ))

    # 7. Error Level Analysis (heuristic)
    try:
        tamper_res = await run_in_threadpool(tampering_service.analyze, pil_doc)
    except Exception as e:
        logger.error(f"Forensics analysis error: {type(e).__name__}")
        tamper_res = TamperAnalysisResult(forensic_notes=["Forensic analysis unavailable."], evidence_state="UNAVAILABLE")
    stages.append(PipelineStage(
        stage="image_forensics_ela",
        status="UNAVAILABLE" if tamper_res.evidence_state == "UNAVAILABLE" else "COMPLETED",
    ))

    # 8. Face detection / comparison
    try:
        face_res = await run_in_threadpool(face_service.verify_faces, cv_doc, cv_person)
    except Exception as e:
        logger.error(f"Face verification error: {type(e).__name__}")
        face_res = FaceVerificationResult(
            match_verdict="NOT_AVAILABLE" if cv_person is not None else "NOT_APPLICABLE",
            notes="Face processing failed.",
            evidence_state="UNAVAILABLE" if cv_person is not None else "NOT_APPLICABLE",
        )
    face_stage_status = {
        "NOT_APPLICABLE": "NOT_APPLICABLE",
        "NOT_AVAILABLE": "UNAVAILABLE",
    }.get(face_res.match_verdict, "COMPLETED")
    stages.append(PipelineStage(stage="face_comparison", status=face_stage_status,
                                detail=f"verdict={face_res.match_verdict}"))

    # 9. Evidence fusion
    try:
        risk_res = risk_engine.evaluate(
            doc_info=doc_info, validation=validation_res, watchlist=watchlist_res,
            tampering=tamper_res, face=face_res
        )
        stages.append(PipelineStage(stage="risk_scoring", status="COMPLETED"))
    except Exception as e:
        logger.error(f"Risk evaluation error: {type(e).__name__}")
        risk_res = RiskAssessment(
            score=50, level="MEDIUM", verdict="INCOMPLETE_SCREENING",
            reasons=["Risk scoring failed; the automated assessment is incomplete."],
            unavailable_signals=["risk_scoring"],
        )
        stages.append(PipelineStage(stage="risk_scoring", status="UNAVAILABLE"))

    elapsed_ms = round((time.time() - start_time) * 1000.0, 1)
    case_id = f"DS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:12].upper()}"

    case = ScreeningResult(
        case_id=case_id,
        timestamp=_now(),
        processing_time_ms=elapsed_ms,
        document_info=doc_info,
        validation=validation_res,
        watchlist=watchlist_res,
        tampering=tamper_res,
        face_verification=face_res,
        risk_assessment=risk_res,
        pipeline=stages,
        document_preview_base64=cv2_to_base64(cv_doc, quality=80),
        person_preview_base64=person_b64,
    )

    # 10. Local persistence (development only). In the Cloudflare deployment the
    # Worker stores a redacted record in D1 and issues the session token.
    if storage_service is not None:
        raw_session_token, session_token_hash = generate_session_token()
        try:
            storage_service.save_case(case, session_token_hash=session_token_hash)
            case.session_token = raw_session_token
            case.persistence = {"status": "STORED", "backend": "sqlite-local",
                                "retention_hours": settings.data_retention_hours, "redacted": True}
        except Exception as e:
            logger.error(f"Case persistence failed: {type(e).__name__}")
            case.persistence = {"status": "FAILED", "backend": "sqlite-local"}
    else:
        case.persistence = {"status": "NOT_STORED", "backend": "none"}

    return case

@router.post(
    "/api/verify-face",
    response_model=FaceVerifyResponse,
    dependencies=[Depends(rate_limit_analysis)]
)
async def verify_face(
    image1: UploadFile = File(..., description="First face image (e.g. ID card portrait)"),
    image2: UploadFile = File(..., description="Second face image (e.g. person photo)")
):
    await _acquire_slot()
    try:
        b1 = await image1.read(settings.max_upload_size_bytes + 1)
        b2 = await image2.read(settings.max_upload_size_bytes + 1)
        validate_image_upload(b1, field_name=sanitize_filename(image1.filename))
        validate_image_upload(b2, field_name=sanitize_filename(image2.filename))
        try:
            cv1 = bytes_to_cv2(b1)
            cv2_img = bytes_to_cv2(b2)
            res = await run_in_threadpool(face_service.verify_faces, cv1, cv2_img)
        except Exception as e:
            logger.error(f"Face verify endpoint error: {type(e).__name__}")
            raise HTTPException(status_code=400, detail="Face comparison failed. Please upload clear face images.")
        return FaceVerifyResponse(
            status="ok",
            similarity_score=res.similarity_score,
            match_verdict=res.match_verdict,
            document_face_detected=res.document_face_detected,
            person_face_detected=res.person_face_detected,
            message=res.notes or "Face comparison completed (similarity is not a calibrated probability)."
        )
    finally:
        analysis_semaphore.release()

# ---------------------------------------------------------
# Case Records & Reviewer Actions (local SQLite mode only)
# ---------------------------------------------------------

def _require_storage():
    if storage_service is None:
        raise HTTPException(status_code=404, detail="Case storage is not enabled on this service.")
    return storage_service

@router.get("/api/case/{case_id}", response_model=ScreeningResult)
async def get_case(
    case_id: str,
    x_session_token: Optional[str] = Header(None),
    x_officer_key: Optional[str] = Header(None)
):
    """Requires the submitter's X-Session-Token or a valid officer key."""
    store = _require_storage()
    case, auth_status = store.get_case_with_auth(
        case_id=case_id,
        session_token=x_session_token,
        is_officer=is_valid_officer_key(x_officer_key),
    )
    # Unknown and unauthorised cases return the same response to prevent enumeration.
    if auth_status in ("FORBIDDEN", "NOT_FOUND") or not case:
        if auth_status == "FORBIDDEN":
            logger.warning("Unauthorized case access attempt.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found or access denied.")
    return case

@router.get("/api/cases", response_model=List[CaseSummary])
async def list_cases(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    officer_token: str = Depends(verify_officer_token)
):
    return _require_storage().list_cases(limit=limit, offset=offset)

@router.post("/api/case/{case_id}/review", response_model=ScreeningResult)
async def submit_officer_review(
    case_id: str,
    payload: OfficerReviewRequest,
    officer_token: str = Depends(verify_officer_token)
):
    """Records a reviewer's assessment. This is an audit record, not a legal determination."""
    store = _require_storage()
    if not store.get_case_record(case_id):
        raise HTTPException(status_code=404, detail="Case not found or access denied.")

    review = OfficerReview(
        reviewed=True,
        officer_id=payload.officer_id,
        officer_name=payload.officer_name,
        decision=payload.decision,
        override_ai_verdict=payload.override_ai_verdict,
        notes=payload.notes,
        timestamp=_now()
    )
    updated_case = store.update_officer_review(case_id, review)
    if not updated_case:
        raise HTTPException(status_code=500, detail="Failed to record review.")
    return updated_case
