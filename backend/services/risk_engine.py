from typing import List, Dict, Any, Optional
from ..models.schemas import (
    ValidationResult,
    WatchlistHit,
    TamperAnalysisResult,
    FaceVerificationResult,
    ExtractedFields,
    RiskAssessment
)

class RiskEngine:
    def evaluate(
        self,
        doc_info: ExtractedFields,
        validation: ValidationResult,
        watchlist: WatchlistHit,
        tampering: TamperAnalysisResult,
        face: Optional[FaceVerificationResult] = None
    ) -> RiskAssessment:
        risk_score = 0.0
        reasons: List[str] = []
        breakdown: Dict[str, float] = {}

        # 1. Watchlist & Registry Evaluation (Weight: up to 80 pts)
        if watchlist.is_flagged:
            if watchlist.status in ["WATCHLIST_HIT", "IMPOSTER_ALERT"]:
                pts = 75.0
                risk_score += pts
                breakdown["watchlist_penalty"] = pts
                reasons.append(f"CRITICAL WATCHLIST HIT: {watchlist.details}")
            elif watchlist.status == "STOLEN_ID_ALERT":
                pts = 70.0
                risk_score += pts
                breakdown["stolen_id_penalty"] = pts
                reasons.append(f"STOLEN/LOST DOCUMENT ALERT: {watchlist.details}")
        else:
            reasons.append("Watchlist & Stolen Registry: Cleared (No negative records found).")

        # 2. Document Format & Checksum Validation (Weight: up to 35 pts)
        if not validation.overall_valid:
            pts = 35.0
            risk_score += pts
            breakdown["validation_failure_penalty"] = pts
            failed_msgs = [f.message for f in validation.checks if not f.passed and f.severity == "critical"]
            for m in failed_msgs:
                reasons.append(f"Document Checksum / Format Failure: {m}")
        else:
            reasons.append(f"Document Structure: Validated ({validation.checks_passed}/{validation.checks_total} checks passed).")

        # Check for expired document
        for f in validation.checks:
            if f.check_name == "Document Expiration Status" and not f.passed:
                pts = 20.0
                risk_score += pts
                breakdown["expired_penalty"] = pts
                reasons.append("Document Expiry: Document validity has lapsed.")

        # 3. Tampering & Image Forensics (Weight: up to 30 pts)
        if tampering.has_anomalies or tampering.ela_score > 40.0:
            # Scale ELA score (0-100) to max 30 pts
            pts = round((tampering.ela_score / 100.0) * 30.0, 1)
            risk_score += pts
            breakdown["tampering_penalty"] = pts
            reasons.append(f"Image Forensics (ELA): Score {tampering.ela_score}/100. Localized compression discontinuities detected in {tampering.anomaly_regions} region(s).")
        else:
            reasons.append("Image Forensics (ELA): Uniform compression distribution. No splicing anomalies detected.")

        # 4. Biometric Face Verification (Weight: up to 40 pts)
        if face:
            if face.match_verdict == "MISMATCH":
                pts = 40.0
                risk_score += pts
                breakdown["biometric_mismatch_penalty"] = pts
                reasons.append(f"Biometric Facial Mismatch: Document photo and live traveller do not match (Similarity: {face.similarity_score}%).")
            elif face.match_verdict == "MATCH":
                reasons.append(f"Biometric Facial Verification: Confirmed match (Similarity: {face.similarity_score}%).")
            elif face.match_verdict == "INDETERMINATE":
                pts = 15.0
                risk_score += pts
                breakdown["biometric_indeterminate_penalty"] = pts
                reasons.append("Biometric Verification: Inconclusive (Face not clearly detected in one or both inputs).")
        else:
            reasons.append("Biometric Verification: Live person image omitted (Document screening only).")

        # 5. Document Completeness
        if doc_info.document_type == "UNKNOWN":
            pts = 20.0
            risk_score += pts
            breakdown["unknown_doc_type_penalty"] = pts
            reasons.append("Document Recognition: Document layout not recognized as supported standard ID.")

        # Cap total risk score between 0 and 100
        final_score = int(min(100.0, max(0.0, round(risk_score))))

        # Determine level & action
        if final_score <= 30:
            level = "LOW"
            verdict = "CLEARED"
            recommendation = "Standard border clearance granted. Proceed."
        elif final_score <= 70:
            level = "MEDIUM"
            verdict = "SECONDARY_INSPECTION"
            recommendation = "Direct traveller to Secondary Inspection Counter for manual document inspection."
        else:
            level = "HIGH"
            verdict = "DETENTION_ALERT"
            recommendation = "Flag for immediate supervisor intervention / detain for fraudulent identity investigation."

        return RiskAssessment(
            score=final_score,
            level=level,
            verdict=verdict,
            reasons=reasons,
            recommended_action=recommendation,
            breakdown=breakdown
        )

risk_engine = RiskEngine()
