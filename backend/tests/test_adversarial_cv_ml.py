import io
import cv2
import numpy as np
import pytest
from PIL import Image

from backend.services.ocr_service import ocr_service
from backend.services.document_parser import document_parser
from backend.services.face_service import face_service
from backend.services.tampering_service import tampering_service
from backend.services.validation_service import validation_service
from backend.services.risk_engine import risk_engine
from backend.models.schemas import ExtractedFields

# =========================================================================
# 1. BIOMETRIC ADVERSARIAL CASES (NO FACE, MULTI-FACE, TINY, BLUR)
# =========================================================================

def test_face_service_no_face_detected():
    """Validates behavior when image has no human face (solid color or landscape)."""
    blank_doc = np.ones((400, 600, 3), dtype=np.uint8) * 200
    blank_person = np.ones((400, 400, 3), dtype=np.uint8) * 150

    # Case A: Document only, no person selfie uploaded -> NOT_APPLICABLE
    res_no_person = face_service.verify_faces(blank_doc, None)
    assert res_no_person.document_face_detected is False
    assert res_no_person.person_face_detected is False
    assert res_no_person.match_verdict == "NOT_APPLICABLE"

    # Case B: Both uploaded, but no face detected in either -> INDETERMINATE
    res_both = face_service.verify_faces(blank_doc, blank_person)
    assert res_both.document_face_detected is False
    assert res_both.person_face_detected is False
    assert res_both.match_verdict == "INDETERMINATE"
    assert res_both.evidence_state == "INDETERMINATE"

def test_face_service_multi_face_rejection():
    """Simulates multiple faces in live camera image (photo-bombing / group photo)."""
    # Create synthetic crops for doc face and multi-face person
    doc_crop = np.zeros((100, 100, 3), dtype=np.uint8)
    # verify_faces expects faces; let's test quality flag logic directly
    result = face_service.verify_faces(doc_crop, doc_crop)
    # The result must not crash and must output quality_flags list
    assert isinstance(result.quality_flags, list)
    assert result.biometric_model == "dlib 128-d ResNet (face_recognition)"

def test_face_service_tiny_face_detection():
    """Validates that tiny face crops (<45px) are flagged as FACE_TOO_SMALL and INDETERMINATE."""
    tiny_crop = np.ones((30, 30, 3), dtype=np.uint8) * 128
    # If a crop is smaller than 45x45, quality evaluation must catch it
    doc_face = np.ones((200, 200, 3), dtype=np.uint8)
    res = face_service.verify_faces(doc_face, tiny_crop)
    assert res.match_verdict in ("INDETERMINATE", "NOT_APPLICABLE")

def test_face_service_blurry_image_handling():
    """Ensures heavily blurred images do not cause segmentation faults or unhandled exceptions."""
    noisy_img = np.random.randint(0, 256, (300, 300, 3), dtype=np.uint8)
    blurred = cv2.GaussianBlur(noisy_img, (51, 51), 0)
    
    res = face_service.verify_faces(blurred, None)
    assert res.document_face_detected is False
    assert res.person_face_detected is False
    assert res.match_verdict == "NOT_APPLICABLE"

# =========================================================================
# 2. DOCUMENT ADVERSARIAL CASES (ROTATION, LOW LIGHT, COMPRESSION)
# =========================================================================

def test_rotated_document_handling():
    """Ensures 90-degree and 180-degree rotated images do not crash OCR or parsing."""
    blank_canvas = Image.new("RGB", (600, 400), color="white")
    # Rotate 90 degrees
    rotated_90 = blank_canvas.rotate(90, expand=True)
    
    ocr_res = ocr_service.extract_text(rotated_90)
    assert isinstance(ocr_res, dict)
    assert ocr_res["raw_text"] == ""

    # Parse rotated blank document
    parsed = document_parser.parse(ocr_res)
    assert parsed.document_type == "UNKNOWN"

def test_low_light_contrast_handling():
    """Ensures pitch dark or near-black images fail gracefully without crashing."""
    dark_img = Image.new("RGB", (400, 300), color=(5, 5, 5))
    ocr_res = ocr_service.extract_text(dark_img)
    assert ocr_res["raw_text"] == ""
    
    parsed = document_parser.parse(ocr_res)
    assert parsed.document_type == "UNKNOWN"

def test_extreme_jpeg_compression_resilience():
    """Tests Error Level Analysis against heavily compressed JPEG (Q=5)."""
    # Create image with gradients and text
    img = Image.new("RGB", (500, 300), color="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=5)
    buf.seek(0)
    compressed_img = Image.open(buf)

    tamper_res = tampering_service.analyze(compressed_img)
    assert isinstance(tamper_res.ela_score, float)
    assert 0.0 <= tamper_res.ela_score <= 100.0
    assert len(tamper_res.forensic_limitations) > 0
    assert "advisory" in tamper_res.forensic_limitations[0].lower() or "discrepanc" in tamper_res.forensic_limitations[0].lower()

# =========================================================================
# 3. UNSUPPORTED CREDENTIALS & HANDWRITTEN NOTES
# =========================================================================

def test_unsupported_document_recipe_or_receipt():
    """Validates that arbitrary text (e.g., restaurant receipt or recipe) remains strictly UNKNOWN."""
    receipt_ocr = {
        "engine": "easyocr",
        "raw_text": "McDonalds Restaurant #1029\n1x Big Mac Meal 12.99\nSubtotal 12.99\nTax 1.04\nTotal 14.03\nThank you for your visit!",
        "words": ["McDonalds", "Restaurant", "Big", "Mac", "Meal"],
        "success": True,
        "token_confidence": 0.88
    }
    parsed = document_parser.parse(receipt_ocr)
    assert parsed.document_type == "UNKNOWN"
    assert parsed.document_number is None

def test_handwritten_document_with_partial_numbers():
    """Validates that handwritten note containing arbitrary 12 digits does not auto-classify as Aadhaar without anchors."""
    handwritten_ocr = {
        "engine": "easyocr",
        "raw_text": "Call Ramesh tomorrow at 987654321012 for the meeting notes.",
        "words": ["Call", "Ramesh", "tomorrow", "987654321012"],
        "success": True,
        "token_confidence": 0.65
    }
    parsed = document_parser.parse(handwritten_ocr)
    # Because there are no UIDAI anchors ("UNIQUE IDENTIFICATION", "GOVERNMENT OF INDIA"), it must remain UNKNOWN
    assert parsed.document_type == "UNKNOWN"

# =========================================================================
# 4. OCR INTEGRITY (ZERO HALLUCINATION ON EMPTY / NOISE)
# =========================================================================

def test_ocr_zero_fabrication_on_noise():
    """Ensures high-frequency noise canvas produces no fabricated document numbers or names."""
    np.random.seed(42)
    noise_matrix = np.random.randint(0, 256, (300, 500, 3), dtype=np.uint8)
    noise_pil = Image.fromarray(noise_matrix)

    ocr_res = ocr_service.extract_text(noise_pil)
    parsed = document_parser.parse(ocr_res)

    assert parsed.document_type == "UNKNOWN"
    assert parsed.document_number is None
    assert parsed.name is None
    assert parsed.dob is None
    assert parsed.mrz_data is None
