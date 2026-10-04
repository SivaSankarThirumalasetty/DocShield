from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.config import settings
from backend.core.rate_limit import InMemoryRateLimiter

client = TestClient(app)
SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"


def test_cloudflare_pages_cors_allowed():
    """Verify Cloudflare Workers and Pages production/preview subdomains are allowed via CORS."""
    for origin in [
        "https://docshield.sivasankar-t1606.workers.dev",
        "https://docshield.pages.dev",
        "https://cloudflare-migration.docshield.pages.dev",
    ]:
        res = client.options(
            "/api/analyze-document",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-Officer-Key",
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == origin


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


def test_cloudflare_forwarded_https_sets_hsts():
    """Verify X-Forwarded-Proto: https from Cloudflare edge triggers Strict-Transport-Security."""
    res = client.get("/api/health", headers={"X-Forwarded-Proto": "https"})
    assert res.status_code == 200
    assert "max-age=31536000" in res.headers.get("strict-transport-security", "")


def test_cf_connecting_ip_extraction():
    """Verify rate limiter extracts true client IP from CF-Connecting-IP header."""
    class DummyReq:
        headers = {"cf-connecting-ip": "203.0.113.42", "x-forwarded-for": "10.0.0.1"}
        client = None

    assert InMemoryRateLimiter._extract_client_ip(DummyReq()) == "203.0.113.42"


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
