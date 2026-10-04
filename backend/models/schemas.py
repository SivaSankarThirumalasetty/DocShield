from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

class EvidenceState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    UNAVAILABLE = "UNAVAILABLE"
    DEMO = "DEMO"

class HealthResponse(BaseModel):
    status: str = 'healthy'
    service: str = 'DocShield Border Screening Engine'
    version: str = '2.0.0-audited'
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
    level: str = 'LOW'  # 'LOW', 'MEDIUM', 'HIGH'
    verdict: str = 'CLEARED'  # 'CLEARED', 'SECONDARY_INSPECTION', 'DETENTION_ALERT'
    reasons: List[str] = Field(default_factory=list)
    recommended_action: str = 'Allow passage'
    breakdown: Dict[str, float] = Field(default_factory=dict)
    evidence_states: Dict[str, str] = Field(default_factory=dict)

class OfficerReview(BaseModel):
    reviewed: bool = False
    officer_id: Optional[str] = None
    officer_name: Optional[str] = None
    decision: Optional[str] = None  # 'CLEARED_FOR_ENTRY', 'SECONDARY_INSPECTION', 'DENIED_ENTRY', 'DETAINED'
    override_ai_verdict: bool = False
    notes: Optional[str] = None
    timestamp: Optional[str] = None

class OfficerReviewRequest(BaseModel):
    officer_id: str
    officer_name: str
    decision: str
    override_ai_verdict: bool = False
    notes: Optional[str] = None

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
