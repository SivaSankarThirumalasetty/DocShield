from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field

class EvidenceState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    UNAVAILABLE = "UNAVAILABLE"
    DEMO = "DEMO"

ADVISORY_NOTICE = (
    "PROTOTYPE / ADVISORY ONLY. DocShield is an AI-assisted document screening prototype. "
    "It is not a government verification service, registry checks use SIMULATED demo data, "
    "and no output is a determination of identity, authenticity, or eligibility. "
    "A qualified human reviewer is responsible for every consequential decision."
)

# Advisory verdicts. None of these authorises, denies, or detains anyone.
Verdict = Literal[
    "NO_ADVERSE_INDICATORS",
    "INCOMPLETE_SCREENING",
    "MANUAL_REVIEW_RECOMMENDED",
    "ESCALATE_FOR_EXPERT_REVIEW",
]

# Reviewer outcomes recorded against a case. These describe the reviewer's own
# assessment of the screening; they are not automated or legal determinations.
ReviewerDecision = Literal[
    "CONCUR_NO_FURTHER_ACTION",
    "REFER_FOR_PHYSICAL_INSPECTION",
    "DOCUMENT_UNVERIFIABLE",
    "ESCALATE_TO_SUPERVISOR",
]

class HealthResponse(BaseModel):
    status: str = 'healthy'
    service: str = 'DocShield Screening Engine (Prototype)'
    version: str = '2.1.0'
    timestamp: str
    modules: Dict[str, bool] = Field(default_factory=dict)
    system_notes: List[str] = Field(default_factory=list)

class ExtractedFields(BaseModel):
    document_type: str = 'UNKNOWN'
    document_number: Optional[str] = None
    name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    expiry_date: Optional[str] = None
    father_or_spouse_name: Optional[str] = None
    address: Optional[str] = None
    mrz_lines: List[str] = Field(default_factory=list)
    mrz_data: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    ocr_confidence: float = 0.0
    evidence_state: str = "INDETERMINATE"
    raw_text_preview: str = ''
    verhoeff_valid: Optional[bool] = Field(default=None, exclude=True)

class ValidationFlag(BaseModel):
    check_name: str
    field: str
    passed: bool
    message: str
    severity: str = 'warning'  # 'info', 'warning', 'critical'
    evidence_state: str = "PASS"

class ValidationResult(BaseModel):
    overall_valid: bool = True
    checks_passed: int = 0
    checks_total: int = 0
    checks: List[ValidationFlag] = Field(default_factory=list)

class WatchlistHit(BaseModel):
    is_flagged: bool = False
    status: str = 'CLEARED'  # 'CLEARED', 'WATCHLIST_HIT', 'STOLEN_ID_ALERT', 'IMPOSTER_ALERT', 'UNAVAILABLE'
    matched_record_id: Optional[str] = None
    matched_name: Optional[str] = None
    watchlist_category: Optional[str] = None
    details: Optional[str] = None
    evidence_state: str = "DEMO"  # DEMO_WATCHLIST default

class TamperAnalysisResult(BaseModel):
    ela_score: float = 0.0  # 0.0 (clean) to 100.0 (high anomaly)
    has_anomalies: bool = False
    anomaly_regions: int = 0
    bounding_boxes: List[List[int]] = Field(default_factory=list)  # [[x, y, w, h], ...]
    ela_image_base64: Optional[str] = None
    analysis_confidence: float = 0.0
    forensic_notes: List[str] = Field(default_factory=list)
    forensic_limitations: List[str] = Field(default_factory=list)
    evidence_state: str = "INDETERMINATE"

class FaceVerificationResult(BaseModel):
    document_face_detected: bool = False
    person_face_detected: bool = False
    similarity_score: float = 0.0  # 0.0 to 100.0
    match_verdict: str = 'NOT_APPLICABLE'  # 'MATCH', 'MISMATCH', 'INDETERMINATE', 'NOT_AVAILABLE', 'NOT_APPLICABLE'
    face_distance: Optional[float] = None
    biometric_model: str = "dlib 128-d ResNet (face_recognition)"
    face_count_doc: int = 0
    face_count_person: int = 0
    quality_flags: List[str] = Field(default_factory=list)
    document_face_crop_base64: Optional[str] = None
    person_face_crop_base64: Optional[str] = None
    notes: Optional[str] = None
    evidence_state: str = "NOT_APPLICABLE"

class RiskAssessment(BaseModel):
    score: int = 0  # 0 to 100
    level: str = 'MEDIUM'  # 'LOW', 'MEDIUM', 'HIGH'
    verdict: Verdict = 'INCOMPLETE_SCREENING'
    reasons: List[str] = Field(default_factory=list)
    recommended_action: str = 'Manual review by a qualified reviewer is required.'
    breakdown: Dict[str, float] = Field(default_factory=dict)
    evidence_states: Dict[str, str] = Field(default_factory=dict)
    # Signals that could not be evaluated. A non-empty list prevents NO_ADVERSE_INDICATORS.
    unavailable_signals: List[str] = Field(default_factory=list)
    score_interpretation: str = (
        "Heuristic, uncalibrated advisory score (0-100). It is NOT a probability of fraud "
        "and has not been validated on a representative dataset."
    )

class OfficerReview(BaseModel):
    reviewed: bool = False
    officer_id: Optional[str] = None
    officer_name: Optional[str] = None
    decision: Optional[ReviewerDecision] = None
    override_ai_verdict: bool = False
    notes: Optional[str] = None
    timestamp: Optional[str] = None

class OfficerReviewRequest(BaseModel):
    officer_id: str = Field(..., min_length=1, max_length=64)
    officer_name: str = Field(..., min_length=1, max_length=128)
    decision: ReviewerDecision
    override_ai_verdict: bool = False
    notes: Optional[str] = Field(default=None, max_length=2000)

class PipelineStage(BaseModel):
    stage: str
    status: Literal["COMPLETED", "FAILED", "UNAVAILABLE", "NOT_APPLICABLE", "SKIPPED"]
    detail: Optional[str] = None

class ScreeningResult(BaseModel):
    case_id: str
    timestamp: str
    processing_time_ms: float
    document_info: ExtractedFields
    validation: ValidationResult
    watchlist: WatchlistHit
    tampering: TamperAnalysisResult
    face_verification: FaceVerificationResult
    risk_assessment: RiskAssessment
    pipeline: List[PipelineStage] = Field(default_factory=list)
    advisory_notice: str = ADVISORY_NOTICE
    # Where (and whether) a redacted case record was stored. Never claims storage that did not happen.
    persistence: Dict[str, Any] = Field(default_factory=lambda: {"status": "NOT_STORED"})
    officer_review: Optional[OfficerReview] = None
    document_preview_base64: Optional[str] = None
    person_preview_base64: Optional[str] = None
    session_token: Optional[str] = None

class FaceVerifyResponse(BaseModel):
    status: str
    similarity_score: float
    match_verdict: str
    document_face_detected: bool
    person_face_detected: bool
    message: str

class CaseSummary(BaseModel):
    case_id: str
    timestamp: str
    document_type: str
    document_number: Optional[str] = None
    risk_score: int
    risk_level: str
    verdict: str
    officer_decision: Optional[str] = None
