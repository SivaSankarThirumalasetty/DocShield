from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.config import settings
from backend.core.rate_limit import InMemoryRateLimiter
import pytest
from backend.services.ocr_service import ocr_service
from backend.services import face_service as face_module

client = TestClient(app)
SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"


def test_local_dev_origin_allowed_production_origins_not_needed():
    """Production is same-origin through the Worker; only the Vite dev origin needs CORS."""
    res = client.options(
        "/api/analyze-document",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert res.headers.get("access-control-allow-credentials") is None


def test_unauthorized_origin_cors_blocked():
    """Verify arbitrary untrusted origins are not granted CORS access."""
    evil_origin = "https://malicious-phishing-site.example.com"
    res = client.options(
        "/api/analyze-document",
        headers={
            "Origin": evil_origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res.headers.get("access-control-allow-origin") != evil_origin
    assert res.headers.get("access-control-allow-origin") != "*"


def test_no_wildcard_in_configured_cors_origins():
    """Ensure wildcard '*' is never present in settings.cors_origins."""
    assert "*" not in settings.cors_origins


def test_cf_connecting_ip_extraction():
    """Verify rate limiter extracts true client IP from CF-Connecting-IP header."""
    class DummyReq:
        headers = {"cf-connecting-ip": "203.0.113.42", "x-forwarded-for": "10.0.0.1"}
        client = None

    assert InMemoryRateLimiter._extract_client_ip(DummyReq()) == "203.0.113.42"


@pytest.mark.skipif(
    not (ocr_service.tesseract_configured and face_module.FACE_REC_AVAILABLE),
    reason="Requires Tesseract and dlib/face_recognition (run inside the backend Docker image).",
)
def test_end_to_end_real_samples_and_verify_face():
    """Execute real sample documents and face verification through the FastAPI pipeline."""
    aadhaar_valid = (SAMPLE_DIR / "aadhaar_valid.png").read_bytes()
    passport_sample = (SAMPLE_DIR / "passport_sample.png").read_bytes()
    person_sample = (SAMPLE_DIR / "sample_person.png").read_bytes()

    # 1. Full document + biometric analysis on valid Aadhaar
    res_aadhaar = client.post(
        "/api/analyze-document",
        files={
            "document": ("aadhaar_valid.png", aadhaar_valid, "image/png"),
            "person_image": ("sample_person.png", person_sample, "image/png"),
        },
        data={"doc_type_hint": "AADHAAR"},
        headers={
            "Origin": "https://docshield.pages.dev",
            "CF-Connecting-IP": "203.0.113.50",
        },
    )
    assert res_aadhaar.status_code == 200
    data_a = res_aadhaar.json()
    assert data_a["document_info"]["document_type"] == "AADHAAR"
    assert data_a["validation"]["overall_valid"] is True
    assert data_a["face_verification"]["document_face_detected"] is True
    assert data_a["face_verification"]["person_face_detected"] is True
    assert data_a["face_verification"]["match_verdict"] == "MATCH"

    # 2. Full document analysis on Passport with MRZ
    res_ppt = client.post(
        "/api/analyze-document",
        files={
            "document": ("passport_sample.png", passport_sample, "image/png"),
        },
        data={"doc_type_hint": "PASSPORT"},
        headers={"CF-Connecting-IP": "203.0.113.51"},
    )
    assert res_ppt.status_code == 200
    data_p = res_ppt.json()
    assert data_p["document_info"]["document_type"] == "PASSPORT"
    assert data_p["document_info"]["mrz_data"] is not None

    # 3. Dedicated 1:1 face verification endpoint
    res_face = client.post(
        "/api/verify-face",
        files={
            "image1": ("aadhaar_valid.png", aadhaar_valid, "image/png"),
            "image2": ("sample_person.png", person_sample, "image/png"),
        },
    )
    assert res_face.status_code == 200
    face_json = res_face.json()
    assert face_json["status"] == "ok"
    assert face_json["match_verdict"] == "MATCH"
    assert face_json["similarity_score"] > 60.0
