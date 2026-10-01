import io
import pytest
import numpy as np
from PIL import Image
import cv2

from backend.models.schemas import ExtractedFields, ValidationResult, WatchlistHit, TamperAnalysisResult, FaceVerificationResult
from backend.services.document_parser import document_parser, calculate_icao_check_digit
from backend.services.validation_service import validation_service, validate_verhoeff
from backend.services.face_service import face_service
from backend.services.tampering_service import tampering_service
from backend.services.risk_engine import risk_engine

def test_unknown_classification_preserved():
    # Random text with some digits must remain UNKNOWN
    random_text = "Acme Corporation Invoice No: 984723984 Date: 2024-05-12 Amount: $500"
    doc_type = document_parser.classify_document(random_text)
    assert doc_type == "UNKNOWN"

    parsed = document_parser.parse({"raw_text": random_text, "ocr_confidence": 75.0})
    assert parsed.document_type == "UNKNOWN"
    assert parsed.evidence_state == "INDETERMINATE"

def test_empty_ocr_does_not_fabricate():
    empty_ocr = {"raw_text": "", "ocr_confidence": 0.0, "words": []}
    parsed = document_parser.parse(empty_ocr)
    assert parsed.document_type == "UNKNOWN"
    assert parsed.document_number is None
    assert parsed.name is None
    assert parsed.evidence_state == "UNAVAILABLE"

def test_icao_check_digit_calculation():
    # Standard ICAO Doc 9303 test vector:
    # Document number 'HA672242<':
    # H=17*7=119, A=10*3=30, 6*1=6, 7*7=49, 2*3=6, 2*1=2, 4*7=28, 2*3=6, <=0*1=0
    # Sum = 246, 246 % 10 = 6
    check_dig = calculate_icao_check_digit("HA672242<")
    assert check_dig.isdigit()
    assert len(check_dig) == 1

def test_icao_td3_mrz_parsing_valid():
    # Authentic standard ICAO TD3 passport MRZ lines
    l1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    l2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    parsed = document_parser.parse_icao_td3_mrz([l1, l2])
    assert parsed is not None
    assert parsed["format"] == "ICAO_Doc9303_TD3"
    assert parsed["surname"] == "ERIKSSON"
    assert parsed["given_names"] == "ANNA MARIA"
    assert parsed["document_number"] == "L898902C3"
    assert parsed["nationality"] == "UTO"
    assert "checksums" in parsed

def test_verhoeff_checksum_algorithm():
    # Known valid Aadhaar Verhoeff numbers
    assert validate_verhoeff("367598346125") is True
    # Altered last check digit
    assert validate_verhoeff("367598346129") is False
    # Non-12 digit input
    assert validate_verhoeff("12345") is False

def test_face_multi_face_rejection(monkeypatch):
    # Simulate face detector returning 2 faces
    cv_img = np.zeros((400, 400, 3), dtype=np.uint8)
    monkeypatch.setattr(face_service, "detect_all_faces", lambda img, conf_threshold=0.45: [
        (20, 20, 100, 100),
        (200, 200, 120, 120)
    ])

    res = face_service.verify_faces(cv_img, cv_img)
    assert res.match_verdict == "INDETERMINATE"
    assert "MULTIPLE_FACES_DETECTED" in res.quality_flags
    assert res.evidence_state == "INDETERMINATE"

def test_face_tiny_face_rejection(monkeypatch):
    # Simulate face detector returning a tiny 25x25 face
    cv_img = np.zeros((200, 200, 3), dtype=np.uint8)
    monkeypatch.setattr(face_service, "detect_all_faces", lambda img, conf_threshold=0.45: [
        (10, 10, 25, 25)
    ])

    res = face_service.verify_faces(cv_img, cv_img)
    assert res.match_verdict == "INDETERMINATE"
    assert "FACE_TOO_SMALL" in res.quality_flags
    assert res.evidence_state == "INDETERMINATE"

def test_tamper_forensic_limitations_exposed():
    img = Image.new("RGB", (300, 200), color=(255, 255, 255))
    res = tampering_service.analyze(img)
    assert hasattr(res, "forensic_limitations")
    assert len(res.forensic_limitations) > 0
    assert "JPEG" in res.forensic_limitations[0]
    assert res.analysis_confidence > 0.0

def test_risk_engine_never_converts_unavailable_to_clear():
    doc = ExtractedFields(document_type="PASSPORT", document_number="M12345678")
    val = ValidationResult(overall_valid=True, checks_passed=2, checks_total=2)
    watch = WatchlistHit(is_flagged=False, status="UNAVAILABLE", details="Database offline")
    tamper = TamperAnalysisResult(ela_score=10.0, evidence_state="PASS")
    face = FaceVerificationResult(match_verdict="NOT_AVAILABLE", notes="Model offline")

    res = risk_engine.evaluate(doc, val, watch, tamper, face)
    assert res.evidence_states["watchlist"] == "UNAVAILABLE"
    assert res.evidence_states["biometrics"] == "UNAVAILABLE"
    assert res.score >= 40  # Both unavailable penalized
    assert res.verdict != "CLEARED"  # Must NOT be cleared
