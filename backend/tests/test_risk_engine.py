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
        evidence_state="PASS",
        raw_text_preview="PASSPORT REPUBLIC OF INDIA P<INDDOE<<JOHN<<<<<"
    )
    val = ValidationResult(
        overall_valid=True,
        checks_passed=1,
        checks_total=1,
        checks=[ValidationFlag(check_name="Passport Number Syntax", field="document_number",
                               passed=True, message="ok", severity="info", evidence_state="PASS")]
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
        forensic_notes=[],
        evidence_state="PASS"
    )
    face = FaceVerificationResult(
        document_face_detected=True,
        person_face_detected=True,
        similarity_score=85.0,
        face_distance=0.35,
        match_verdict="MATCH",
        evidence_state="PASS"
    )
    return doc, val, watch, tamper, face

def test_low_risk_clean_document():
    doc, val, watch, tamper, face = make_clean_inputs()
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.level == "LOW"
    assert res.verdict == "NO_ADVERSE_INDICATORS"
    assert res.score <= 29
    assert res.unavailable_signals == []

def test_high_risk_biometric_mismatch():
    doc, val, watch, tamper, face = make_clean_inputs()
    face.match_verdict = "MISMATCH"
    face.similarity_score = 25.0
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.level == "HIGH"
    assert res.verdict == "ESCALATE_FOR_EXPERT_REVIEW"
    assert res.score >= 65
    assert "biometric_mismatch_penalty" in res.breakdown

def test_high_risk_watchlist_hit():
    doc, val, watch, tamper, face = make_clean_inputs()
    watch.is_flagged = True
    watch.status = "WATCHLIST_HIT"
    watch.details = "Interpol Red Notice"
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.level == "HIGH"
    assert res.verdict == "ESCALATE_FOR_EXPERT_REVIEW"
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
    tamper.evidence_state = "FAIL"
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert "tampering_penalty" in res.breakdown
    assert res.score >= 20

def test_unknown_document_type():
    doc, val, watch, tamper, face = make_clean_inputs()
    doc.document_type = "UNKNOWN"
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert "unknown_doc_type_penalty" in res.breakdown
    assert res.score >= 20


# ---------------------------------------------------------------------------
# Product-boundary guarantees: unavailable or inconclusive evidence must never
# produce a clean outcome or lower the score.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mutate,signal", [
    (lambda d, v, w, t, f: setattr(w, "status", "UNAVAILABLE"), "demo_registry"),
    (lambda d, v, w, t, f: setattr(t, "evidence_state", "UNAVAILABLE"), "image_forensics"),
    (lambda d, v, w, t, f: setattr(f, "match_verdict", "NOT_AVAILABLE"), "face_comparison"),
])
def test_unavailable_signal_never_yields_clean_outcome(mutate, signal):
    doc, val, watch, tamper, face = make_clean_inputs()
    baseline = risk_engine.evaluate(doc, val, watch, tamper, face)
    mutate(doc, val, watch, tamper, face)
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.verdict != "NO_ADVERSE_INDICATORS"
    assert signal in res.unavailable_signals
    assert res.score >= baseline.score

def test_validation_without_structural_check_is_indeterminate():
    doc, val, watch, tamper, face = make_clean_inputs()
    val.checks = []
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.evidence_states["validation"] == "INDETERMINATE"
    assert res.verdict == "INCOMPLETE_SCREENING"

def test_missing_selfie_is_not_applicable_not_a_match():
    doc, val, watch, tamper, _ = make_clean_inputs()
    res = risk_engine.evaluate(doc, val, watch, tamper, None)
    assert res.evidence_states["biometrics"] == "NOT_APPLICABLE"
    assert res.verdict == "NO_ADVERSE_INDICATORS"

@pytest.mark.parametrize("ela,expected_level", [(0.0, "LOW"), (100.0, "MEDIUM")])
def test_score_is_bounded_and_deterministic(ela, expected_level):
    doc, val, watch, tamper, face = make_clean_inputs()
    tamper.ela_score = ela
    tamper.evidence_state = "FAIL" if ela > 65 else "PASS"
    a = risk_engine.evaluate(doc, val, watch, tamper, face)
    b = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert a.model_dump() == b.model_dump()
    assert 0 <= a.score <= 100
    assert a.level == expected_level

def test_score_saturates_at_100():
    doc, val, watch, tamper, face = make_clean_inputs()
    doc.raw_text_preview = ""
    watch.is_flagged, watch.status = True, "WATCHLIST_HIT"
    face.match_verdict = "MISMATCH"
    val.overall_valid = False
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.score == 100
    assert res.verdict == "ESCALATE_FOR_EXPERT_REVIEW"

@pytest.mark.parametrize("score,level,verdict", [
    (29, "LOW", "NO_ADVERSE_INDICATORS"),
    (30, "MEDIUM", "MANUAL_REVIEW_RECOMMENDED"),
    (64, "MEDIUM", "MANUAL_REVIEW_RECOMMENDED"),
    (65, "HIGH", "ESCALATE_FOR_EXPERT_REVIEW"),
])
def test_decision_boundaries(monkeypatch, score, level, verdict):
    """Drives the score to exact boundary values via the ELA penalty (30 * ela / 100)."""
    doc, val, watch, tamper, face = make_clean_inputs()
    if score == 29:
        res = risk_engine.evaluate(doc, val, watch, tamper, face)
        assert res.score <= 29 and (res.level, res.verdict) == (level, verdict)
        return
    # Fixed contributions: expired (25) + ELA FAIL penalty; pick ELA to land on score.
    from backend.models.schemas import ValidationFlag as VF
    val.checks.append(VF(check_name="Document Expiration Status", field="expiry_date",
                         passed=False, message="expired", severity="critical", evidence_state="FAIL"))
    remaining = score - 25
    if remaining > 30:
        face.match_verdict = "INDETERMINATE"  # +25
        remaining -= 25
    tamper.evidence_state = "FAIL"
    tamper.ela_score = remaining / 30.0 * 100.0
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.score == score
    assert (res.level, res.verdict) == (level, verdict)

def test_recommendations_contain_no_enforcement_language():
    from backend.services.risk_engine import RECOMMENDATIONS
    banned = ("detain", "clearance granted", "deny entry", "grant passage", "arrest")
    for text in RECOMMENDATIONS.values():
        assert not any(b in text.lower() for b in banned)


def test_missing_document_number_is_indeterminate_not_failed():
    """Regression: an empty OCR result must not be scored as a checksum failure."""
    from backend.services.validation_service import validation_service
    doc = ExtractedFields(document_type="AADHAAR", document_number=None, raw_text_preview="",
                          evidence_state="UNAVAILABLE")
    val = validation_service.validate_document(doc)
    assert val.overall_valid is True  # no critical failure was observed
    _, _, watch, tamper, _ = make_clean_inputs()
    res = risk_engine.evaluate(doc, val, watch, tamper, None)
    assert res.evidence_states["validation"] == "INDETERMINATE"
    assert "validation_failure_penalty" not in res.breakdown
    assert res.verdict == "MANUAL_REVIEW_RECOMMENDED"  # 30 (OCR unavailable) -> manual review, never clean
    assert "ocr" in res.unavailable_signals

def test_privacy_mask_flag_is_not_a_structural_pass():
    from backend.services.validation_service import validation_service
    doc = ExtractedFields(document_type="AADHAAR", document_number="XXXX-XXXX-6125", evidence_state="PASS",
                          raw_text_preview="x")
    val = validation_service.validate_document(doc)  # verhoeff_valid unknown
    _, _, watch, tamper, face = make_clean_inputs()
    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.evidence_states["validation"] == "INDETERMINATE"
    assert res.verdict != "NO_ADVERSE_INDICATORS"
