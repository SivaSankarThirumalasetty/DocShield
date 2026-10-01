import pytest
from datetime import datetime
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
from backend.services.storage_service import StorageService

@pytest.fixture
def temp_storage(tmp_path):
    db_file = tmp_path / "test_docshield.db"
    return StorageService(db_url=f"sqlite:///{db_file}")

def make_test_case(case_id="DS-TEST-001"):
    return ScreeningResult(
        case_id=case_id,
        timestamp=datetime.utcnow().isoformat(),
        processing_time_ms=120.5,
        document_info=ExtractedFields(
            document_type="PASSPORT",
            document_number="A12345678",
            name="TEST TRAVELLER",
            dob="1995-05-15"
        ),
        validation=ValidationResult(overall_valid=True, checks_passed=3, checks_total=3),
        watchlist=WatchlistHit(is_flagged=False, status="CLEARED"),
        tampering=TamperAnalysisResult(ela_score=10.0),
        face_verification=FaceVerificationResult(
            document_face_detected=True,
            person_face_detected=True,
            similarity_score=90.0,
            match_verdict="MATCH"
        ),
        risk_assessment=RiskAssessment(
            score=15,
            level="LOW",
            verdict="CLEARED"
        )
    )

def test_save_and_get_case(temp_storage):
    case = make_test_case("DS-2026-TEST1")
    assert temp_storage.save_case(case) is True

    fetched = temp_storage.get_case("DS-2026-TEST1")
    assert fetched is not None
    assert fetched.case_id == "DS-2026-TEST1"
    assert fetched.document_info.document_number == "A12345678"
    assert fetched.risk_assessment.score == 15

def test_list_cases(temp_storage):
    for i in range(3):
        temp_storage.save_case(make_test_case(f"DS-BATCH-{i}"))

    cases = temp_storage.list_cases(limit=10)
    assert len(cases) == 3
    assert any(c.case_id == "DS-BATCH-0" for c in cases)

def test_update_officer_review(temp_storage):
    case = make_test_case("DS-REVIEW-01")
    temp_storage.save_case(case)

    review = OfficerReview(
        reviewed=True,
        officer_id="OFFICER-007",
        officer_name="Agent Smith",
        decision="CLEARED_FOR_ENTRY",
        notes="Physical inspection confirmed holographic watermark."
    )

    updated = temp_storage.update_officer_review("DS-REVIEW-01", review)
    assert updated is not None
    assert updated.officer_review.reviewed is True
    assert updated.officer_review.officer_id == "OFFICER-007"
    assert updated.officer_review.decision == "CLEARED_FOR_ENTRY"
