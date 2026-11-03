from typing import List, Dict, Optional
from ..models.schemas import (
    ValidationResult,
    WatchlistHit,
    TamperAnalysisResult,
    FaceVerificationResult,
    ExtractedFields,
    RiskAssessment
)

# Score bands for the heuristic advisory score. These thresholds are design
# choices, not calibrated decision boundaries; see docs/PRODUCT_LIMITATIONS.md.
HIGH_THRESHOLD = 65
MEDIUM_THRESHOLD = 30

RECOMMENDATIONS = {
    "NO_ADVERSE_INDICATORS": (
        "No adverse indicators were found by the automated checks that ran. This is not a "
        "verification of identity or authenticity; apply your organisation's standard review."
    ),
    "INCOMPLETE_SCREENING": (
        "One or more checks could not be completed, so the automated screening is incomplete. "
        "A qualified reviewer must examine the document manually."
    ),
    "MANUAL_REVIEW_RECOMMENDED": (
        "Automated checks raised indicators that warrant manual review of the document by a "
        "qualified reviewer."
    ),
    "ESCALATE_FOR_EXPERT_REVIEW": (
        "Automated checks raised strong indicators. Refer the document to a senior or "
        "forensic document examiner before any decision is made."
    ),
}


def _validation_state(validation: ValidationResult) -> str:
    """PASS only when a document-number / MRZ format or checksum check actually passed."""
    if not validation.overall_valid:
        return "FAIL"
    structural = [
        c for c in validation.checks
        if c.field in ("document_number", "mrz_lines") and c.evidence_state in ("PASS", "FAIL")
    ]
    if structural and all(c.passed for c in structural):
        return "PASS"
    return "INDETERMINATE"


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
        unavailable: List[str] = []

        def add(key: str, pts: float, reason: str):
            nonlocal risk_score
            risk_score += pts
            breakdown[key] = pts
            reasons.append(reason)

        # 1. OCR & document recognition
        ocr_state = doc_info.evidence_state or "INDETERMINATE"
        if ocr_state == "UNAVAILABLE" or not doc_info.raw_text_preview:
            ocr_state = "UNAVAILABLE"
            unavailable.append("ocr")
            add("ocr_unreadable_penalty", 30.0,
                "OCR: no readable text was extracted, so document fields could not be checked.")
        elif doc_info.document_type == "UNKNOWN":
            ocr_state = "INDETERMINATE"
            add("unknown_doc_type_penalty", 20.0,
                "Document recognition: layout not recognised as a supported document type.")
        else:
            reasons.append(
                f"Document recognition: layout classified as {doc_info.document_type} "
                f"(mean OCR token confidence {doc_info.ocr_confidence}%)."
            )
        evidence_states["ocr"] = ocr_state

        # 2. Simulated registry (never converts UNAVAILABLE into a clean record)
        if watchlist.status == "UNAVAILABLE":
            evidence_states["watchlist"] = "UNAVAILABLE"
            unavailable.append("demo_registry")
            add("registry_unavailable_penalty", 20.0,
                "Simulated registry: the DEMO dataset was unavailable; no registry result exists.")
        elif watchlist.is_flagged:
            evidence_states["watchlist"] = "FAIL"
            if watchlist.status in ("WATCHLIST_HIT", "IMPOSTER_ALERT"):
                add("watchlist_penalty", 75.0,
                    f"SIMULATED registry match (DEMO data, not a real watchlist): {watchlist.details}")
            elif watchlist.status == "STOLEN_ID_ALERT":
                add("stolen_id_penalty", 70.0,
                    f"SIMULATED lost/stolen record match (DEMO data): {watchlist.details}")
        else:
            evidence_states["watchlist"] = "DEMO"
            reasons.append(
                "Simulated registry: no match in the 7-record DEMO dataset. This is not a "
                "real government, police, or watchlist lookup."
            )

        # 3. Face comparison (never converts unavailable into a match)
        if face is None or face.match_verdict == "NOT_APPLICABLE":
            evidence_states["biometrics"] = "NOT_APPLICABLE"
            reasons.append("Face comparison: not applicable (no person photo was supplied).")
        elif face.match_verdict == "NOT_AVAILABLE":
            evidence_states["biometrics"] = "UNAVAILABLE"
            unavailable.append("face_comparison")
            add("biometric_unavailable_penalty", 20.0,
                "Face comparison: the face-embedding model is unavailable; compare faces manually.")
        elif face.match_verdict == "MISMATCH":
            evidence_states["biometrics"] = "FAIL"
            add("biometric_mismatch_penalty", 65.0,
                f"Face comparison: embedding distance {face.face_distance} exceeds the 0.60 "
                "threshold (faces may not belong to the same person; similarity is not a calibrated probability).")
        elif face.match_verdict == "INDETERMINATE":
            evidence_states["biometrics"] = "INDETERMINATE"
            add("biometric_indeterminate_penalty", 25.0,
                f"Face comparison inconclusive: {face.notes or 'face not usable'}.")
        elif face.match_verdict == "MATCH":
            evidence_states["biometrics"] = "PASS"
            reasons.append(
                f"Face comparison: embedding distance {face.face_distance} is within the 0.60 "
                "threshold. This is a similarity signal, not proof of identity."
            )

        # 4. Format / checksum validation
        val_state = _validation_state(validation)
        evidence_states["validation"] = val_state
        if val_state == "FAIL":
            add("validation_failure_penalty", 35.0, "Validation: one or more critical format/checksum checks failed.")
            for f in validation.checks:
                if not f.passed and f.severity == "critical":
                    reasons.append(f"Validation failure: {f.message}")
        elif val_state == "INDETERMINATE":
            reasons.append("Validation: no document-number format or checksum check could be completed.")
        else:
            reasons.append(
                f"Validation: {validation.checks_passed}/{validation.checks_total} format/checksum checks passed."
            )

        for f in validation.checks:
            if f.check_name == "Document Expiration Status" and not f.passed and f.severity == "critical":
                add("expired_penalty", 25.0, "Expiry: the extracted expiry date is in the past.")
                break

        # 5. Error Level Analysis (heuristic)
        tamper_state = tampering.evidence_state or "INDETERMINATE"
        evidence_states["tampering"] = tamper_state
        if tamper_state == "UNAVAILABLE":
            unavailable.append("image_forensics")
            add("tampering_unavailable_penalty", 10.0, "Image forensics (ELA): analysis was unavailable.")
        elif tamper_state == "FAIL":
            pts = round((tampering.ela_score / 100.0) * 30.0, 1)
            add("tampering_penalty", pts,
                f"Image forensics (ELA, heuristic): score {tampering.ela_score}/100 with "
                f"{tampering.anomaly_regions} region(s) of compression inconsistency. ELA is not proof of forgery.")
        elif tamper_state == "INDETERMINATE":
            add("tampering_advisory_penalty", 15.0,
                f"Image forensics (ELA, heuristic): score {tampering.ela_score}/100 is inconclusive.")
        else:
            reasons.append(
                f"Image forensics (ELA, heuristic): score {tampering.ela_score}/100, no significant "
                "compression inconsistencies. ELA cannot rule out tampering."
            )

        final_score = int(min(100.0, max(0.0, round(risk_score))))

        # Essential signals that must be conclusive before a clean outcome is allowed.
        inconclusive = [
            k for k in ("ocr", "validation", "tampering", "biometrics")
            if evidence_states.get(k) in ("INDETERMINATE", "UNAVAILABLE")
        ]

        if final_score >= HIGH_THRESHOLD:
            level, verdict = "HIGH", "ESCALATE_FOR_EXPERT_REVIEW"
        elif final_score >= MEDIUM_THRESHOLD:
            level, verdict = "MEDIUM", "MANUAL_REVIEW_RECOMMENDED"
        elif unavailable or inconclusive:
            level, verdict = "MEDIUM", "INCOMPLETE_SCREENING"
            reasons.append(
                "Outcome withheld: the following signals were unavailable or inconclusive: "
                + ", ".join(sorted(set(unavailable + inconclusive))) + "."
            )
        else:
            level, verdict = "LOW", "NO_ADVERSE_INDICATORS"

        return RiskAssessment(
            score=final_score,
            level=level,
            verdict=verdict,
            reasons=reasons,
            recommended_action=RECOMMENDATIONS[verdict],
            breakdown=breakdown,
            evidence_states=evidence_states,
            unavailable_signals=sorted(set(unavailable)),
        )

risk_engine = RiskEngine()
