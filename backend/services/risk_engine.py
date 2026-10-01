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
        evidence_states: Dict[str, str] = {}

        # 1. OCR & Document Recognition Evidence State
        ocr_state = doc_info.evidence_state or "INDETERMINATE"
        evidence_states["ocr"] = ocr_state
        if ocr_state == "UNAVAILABLE" or not doc_info.raw_text_preview:
            pts = 30.0
            risk_score += pts
            breakdown["ocr_unreadable_penalty"] = pts
            reasons.append("Optical Character Recognition (OCR): Text unreadable or OCR service returned no characters.")
        elif ocr_state == "INDETERMINATE" and doc_info.document_type == "UNKNOWN":
            pts = 20.0
            risk_score += pts
            breakdown["unknown_doc_type_penalty"] = pts
            reasons.append("Document Recognition: Document layout not recognized as supported standard credential.")
        else:
            reasons.append(f"Document Recognition: Layout recognized as {doc_info.document_type} (OCR Confidence: {doc_info.ocr_confidence}%).")

        # 2. Watchlist & Registry Evaluation (Never converts UNAVAILABLE to CLEAR)
        if watchlist.status == "UNAVAILABLE":
            evidence_states["watchlist"] = "UNAVAILABLE"
            pts = 20.0
            risk_score += pts
            breakdown["registry_unavailable_penalty"] = pts
            reasons.append("Watchlist Check: Security database check UNAVAILABLE; clearance withheld.")
        elif watchlist.is_flagged:
            evidence_states["watchlist"] = "FAIL"
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
            evidence_states["watchlist"] = "DEMO"  # DEMO_WATCHLIST
            reasons.append("Watchlist Check: Cleared against local DEMO_WATCHLIST dataset (Non-authoritative).")

        # 3. Biometric Facial Verification (Never converts UNAVAILABLE to MATCH)
        if face is None or face.match_verdict == "NOT_APPLICABLE":
            evidence_states["biometrics"] = "NOT_APPLICABLE"
            reasons.append("Biometric Verification: Live person image omitted (Document screening only).")
        elif face.match_verdict == "NOT_AVAILABLE":
            evidence_states["biometrics"] = "UNAVAILABLE"
            pts = 20.0
            risk_score += pts
            breakdown["biometric_unavailable_penalty"] = pts
            reasons.append("Biometric Verification: Deep embedding engine is OFFLINE; manual comparison required.")
        elif face.match_verdict == "MISMATCH":
            evidence_states["biometrics"] = "FAIL"
            pts = 65.0
            risk_score += pts
            breakdown["biometric_mismatch_penalty"] = pts
            reasons.append(f"CRITICAL BIOMETRIC MISMATCH: Traveller does not match document portrait (Similarity: {face.similarity_score}%).")
        elif face.match_verdict == "INDETERMINATE":
            evidence_states["biometrics"] = "INDETERMINATE"
            pts = 25.0
            risk_score += pts
            breakdown["biometric_indeterminate_penalty"] = pts
            reasons.append(f"Biometric Verification Inconclusive: {face.notes or 'Face unreadable or quality too low'}.")
        elif face.match_verdict == "MATCH":
            evidence_states["biometrics"] = "PASS"
            reasons.append(f"Biometric Facial Verification: Facial comparison consistent with document (Similarity: {face.similarity_score}%).")

        # 4. Checksum & Format Validation Evidence State
        if not validation.overall_valid:
            evidence_states["validation"] = "FAIL"
            pts = 35.0
            risk_score += pts
            breakdown["validation_failure_penalty"] = pts
            failed_msgs = [f.message for f in validation.checks if not f.passed and f.severity == "critical"]
            for m in failed_msgs:
                reasons.append(f"Validation Failure: {m}")
        else:
            evidence_states["validation"] = "PASS"
            reasons.append(f"Document Structure: Validated ({validation.checks_passed}/{validation.checks_total} checks passed).")

        # Expiration Check
        for f in validation.checks:
            if f.check_name == "Document Expiration Status" and not f.passed:
                pts = 25.0
                risk_score += pts
                breakdown["expired_penalty"] = pts
                reasons.append("Document Expiry: Document validity has expired.")
                break

        # 5. Tampering & Image Forensics Evidence State
        tamper_state = tampering.evidence_state or "INDETERMINATE"
        evidence_states["tampering"] = tamper_state
        if tamper_state == "FAIL" or tampering.ela_score > 55.0:
            pts = round((tampering.ela_score / 100.0) * 30.0, 1)
            risk_score += pts
            breakdown["tampering_penalty"] = pts
            reasons.append(f"Image Forensics (ELA): Score {tampering.ela_score}/100. Significant compression discrepancies in {tampering.anomaly_regions} patch(es).")
        elif tamper_state == "INDETERMINATE" and tampering.ela_score > 35.0:
            pts = 15.0
            risk_score += pts
            breakdown["tampering_advisory_penalty"] = pts
            reasons.append(f"Image Forensics (ELA): Score {tampering.ela_score}/100. Moderate localized error-level variance.")
        elif tamper_state == "UNAVAILABLE":
            pts = 10.0
            risk_score += pts
            breakdown["tampering_unavailable_penalty"] = pts
            reasons.append("Image Forensics: Forensic compression check was UNAVAILABLE.")
        else:
            reasons.append("Image Forensics: Uniform compression profile consistent with authentic capture.")

        # Cap total risk score between 0 and 100
        final_score = int(min(100.0, max(0.0, round(risk_score))))

        # Determine level & action
        if final_score <= 29:
            level = "LOW"
            verdict = "CLEARED"
            recommendation = "Standard border clearance granted. Proceed."
        elif final_score <= 64:
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
            breakdown=breakdown,
            evidence_states=evidence_states
        )

risk_engine = RiskEngine()
