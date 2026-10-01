import pytest
from backend.models.schemas import (
    ExtractedFields,
    ValidationResult,
    ValidationFlag,
    WatchlistHit,
    TamperAnalysisResult,
    FaceVerificationResult
)
from backend.services.risk_engine import risk_engine

def make_clean_inputs():
    doc = ExtractedFields(
        document_type="PASSPORT",
        document_number="M12345678",
        name="JOHN DOE",
        dob="1990-01-01",
        raw_text_preview="PASSPORT REPUBLIC OF INDIA P<INDDOE<<JOHN<<<<<"
    )
    val = ValidationResult(
        overall_valid=True,
        checks_passed=4,
        checks_total=4,
        checks=[]
    )
    watch = WatchlistHit(
        is_flagged=False,
        status="CLEARED",
        details="Cleared in local demo dataset"
    )
    tamper = TamperAnalysisResult(
        ela_score=15.0,
        has_anomalies=False,
        anomaly_regions=0,
        bounding_boxes=[],
        forensic_notes=[]
    )
    face = FaceVerificationResult(
        document_face_detected=True,
        person_face_detected=True,
        similarity_score=85.0,
        match_verdict="MATCH"
    )
    return doc, val, watch, tamper, face

def test_low_risk_clean_document():
    doc, val, watch, tamper, face = make_clean_inputs()
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.level == "LOW"
    assert res.verdict == "CLEARED"
    assert res.score <= 29

def test_high_risk_biometric_mismatch():
    doc, val, watch, tamper, face = make_clean_inputs()
    face.match_verdict = "MISMATCH"
    face.similarity_score = 25.0
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.level == "HIGH"
    assert res.verdict == "DETENTION_ALERT"
    assert res.score >= 65
    assert "biometric_mismatch_penalty" in res.breakdown

def test_high_risk_watchlist_hit():
    doc, val, watch, tamper, face = make_clean_inputs()
    watch.is_flagged = True
    watch.status = "WATCHLIST_HIT"
    watch.details = "Interpol Red Notice"
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.level == "HIGH"
    assert res.verdict == "DETENTION_ALERT"
    assert res.score >= 70

def test_medium_risk_expired_document():
    doc, val, watch, tamper, face = make_clean_inputs()
    val.checks.append(ValidationFlag(
        check_name="Document Expiration Status",
        field="expiry_date",
        passed=False,
        message="Document expired",
        severity="critical"
    ))
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.level == "LOW" or res.level == "MEDIUM"
    assert "expired_penalty" in res.breakdown

def test_missing_ocr_penalized():
    doc, val, watch, tamper, face = make_clean_inputs()
    doc.raw_text_preview = ""  # No OCR text
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert "ocr_unreadable_penalty" in res.breakdown
    assert res.score >= 30

def test_missing_database_not_cleared():
    doc, val, watch, tamper, face = make_clean_inputs()
    watch.status = "UNAVAILABLE"
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert "registry_unavailable_penalty" in res.breakdown
    assert res.score >= 20

def test_missing_face_indeterminate():
    doc, val, watch, tamper, face = make_clean_inputs()
    face.match_verdict = "INDETERMINATE"
    face.notes = "Face not detected in ID"
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert "biometric_indeterminate_penalty" in res.breakdown
    assert res.score >= 25

def test_tamper_signal_anomaly():
    doc, val, watch, tamper, face = make_clean_inputs()
    tamper.has_anomalies = True
    tamper.ela_score = 75.0
    tamper.anomaly_regions = 2
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert "tampering_penalty" in res.breakdown
    assert res.score >= 20

def test_unknown_document_type():
    doc, val, watch, tamper, face = make_clean_inputs()
    doc.document_type = "UNKNOWN"
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert "unknown_doc_type_penalty" in res.breakdown
    assert res.score >= 20
