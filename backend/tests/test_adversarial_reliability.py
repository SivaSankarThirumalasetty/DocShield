import os
import asyncio
import pytest
from backend.services.storage_service import StorageService, storage_service
from backend.services.mock_database import MockDatabaseService
from backend.services.risk_engine import risk_engine
from backend.models.schemas import (
    ScreeningResult,
    ExtractedFields,
    ValidationResult,
    WatchlistHit,
    TamperAnalysisResult,
    FaceVerificationResult,
    RiskAssessment,
    OfficerReview
)

# =========================================================================
# 1. DATABASE COLD RESTART PERSISTENCE
# =========================================================================

def test_persistence_across_cold_restart(tmp_path):
    """
    Verifies that cases, officer reviews, and cryptographic session token hashes
    persist across complete application / service restarts.
    """
    db_file = tmp_path / "restart_test.db"
    db_url = f"sqlite:///{db_file}"

    # Step 1: Start initial service instance and write a case
    service_1 = StorageService(db_url=db_url)
    
    screening = ScreeningResult(
        case_id="DOC-RESTART-001",
        timestamp="2026-10-01T12:00:00Z",
        processing_time_ms=150.5,
        document_info=ExtractedFields(document_type="PASSPORT", document_number="Z1234567", name="Adversarial Tester"),
        validation=ValidationResult(overall_valid=True, checks_passed=3, checks_total=3),
        watchlist=WatchlistHit(is_flagged=False, status="CLEARED"),
        tampering=TamperAnalysisResult(ela_score=12.0),
        face_verification=FaceVerificationResult(similarity_score=92.0, match_verdict="MATCH"),
        risk_assessment=RiskAssessment(score=10, level="LOW", verdict="CLEARED"),
        officer_review=OfficerReview(reviewed=True, officer_name="Commander Sharma", decision="CLEARED_FOR_ENTRY")
    )
    
    from backend.core.security import generate_session_token
    raw_token, token_hash = generate_session_token()
    saved = service_1.save_case(screening, session_token_hash=token_hash)
    assert saved is True

    # Step 2: Simulate application shutdown and cold reboot
    del service_1

    # Step 3: Re-instantiate storage service pointing to same persistent DB
    service_2 = StorageService(db_url=db_url)
    
    # Verify case can be retrieved using original session token
    retrieved, auth_status = service_2.get_case_with_auth("DOC-RESTART-001", session_token=raw_token)
    assert auth_status is None
    assert retrieved is not None
    assert retrieved.case_id == "DOC-RESTART-001"
    assert retrieved.document_info.document_number == "Z1234567"
    assert retrieved.officer_review.reviewed is True
    assert retrieved.officer_review.officer_name == "Commander Sharma"

    # Verify listing cases works on reboot
    all_cases = service_2.list_cases()
    assert len(all_cases) >= 1
    assert any(c.case_id == "DOC-RESTART-001" for c in all_cases)

# =========================================================================
# 2. MISSING OR CORRUPTED DATABASE TOLERANCE
# =========================================================================

def test_missing_mock_database_tolerance(tmp_path):
    """Ensures that if the JSON watchlist file is missing or corrupted, the service returns UNAVAILABLE without crashing."""
    empty_file = tmp_path / "corrupted_watchlist.json"
    empty_file.write_text("{ corrupt json ", encoding="utf-8")

    db = MockDatabaseService(data_path=str(empty_file))
    hit = db.check_watchlist("Any Name", "Any Doc")
    assert hit.status == "UNAVAILABLE"
    assert hit.is_flagged is False
    assert hit.evidence_state == "UNAVAILABLE"

# =========================================================================
# 3. TOTAL PIPELINE DEGRADATION RESILIENCE
# =========================================================================

def test_risk_engine_handles_total_service_failure():
    """
    Tests edge case where OCR, Checksums, Forensics, and Biometrics all fail or error out simultaneously.
    The risk engine must return a valid high-risk advisory verdict, NOT raise an unhandled exception.
    """
    doc_info = ExtractedFields(document_type="UNKNOWN")
    validation = ValidationResult(overall_valid=False, checks_passed=0, checks_total=1)
    watchlist = WatchlistHit(status="UNAVAILABLE", is_flagged=False)
    tamper = TamperAnalysisResult(ela_score=0.0, forensic_notes=["Analysis failed"])
    face = FaceVerificationResult(match_verdict="INDETERMINATE", notes="Face module failure")

    risk = risk_engine.evaluate(
        doc_info=doc_info,
        validation=validation,
        watchlist=watchlist,
        tampering=tamper,
        face=face
    )

    assert isinstance(risk, RiskAssessment)
    assert risk.score >= 50, f"Expected elevated risk score on total degradation, got {risk.score}"
    assert risk.verdict in ("SECONDARY_INSPECTION", "DETENTION_ALERT")
    assert len(risk.reasons) > 0
    # Unavailable signals must not be converted to CLEAR
    assert "UNAVAILABLE" in risk.reasons[0] or any("UNAVAILABLE" in r or "Indeterminate" in r for r in risk.reasons)
